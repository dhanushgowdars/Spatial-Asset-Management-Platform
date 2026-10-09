"""Untrusted KML and zipped Shapefile ingestion with projected metric measurements.

This module has no database or HTTP dependencies. It is suitable for unit tests
and reuse by FastAPI upload handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from math import isfinite
from pathlib import PurePosixPath
from typing import Any
import re
import zipfile

from defusedxml import ElementTree as SafeET
from pyproj import CRS, Transformer
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import transform as transform_geometry
from shapely.validation import explain_validity
import shapefile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_FEATURES = 5000
MAX_VERTICES = 250000
MAX_ZIP_FILES = 40


class InvalidGeospatialUpload(ValueError):
    """Raised when an upload cannot safely be accepted or parsed."""


@dataclass(frozen=True)
class RawFeature:
    id: str
    geometry: Any  # Shapely BaseGeometry or None
    properties: dict[str, Any]
    source_crs: CRS | None


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _children(node: Any, local: str) -> list[Any]:
    return [elem for elem in node if _local_name(elem.tag) == local]


def _descendants(node: Any, local: str) -> list[Any]:
    return [elem for elem in node.iter() if _local_name(elem.tag) == local]


def _first_child(node: Any, local: str) -> Any | None:
    return next(iter(_children(node, local)), None)


def _first_text(node: Any, local: str) -> str | None:
    element = _first_child(node, local)
    return element.text.strip() if element is not None and element.text else None


def _coordinates(node: Any) -> list[tuple[float, float]]:
    coord_node = next((x for x in node.iter() if _local_name(x.tag) == 'coordinates'), None)
    if coord_node is None or not coord_node.text:
        raise ValueError('Missing KML coordinates')
    result: list[tuple[float, float]] = []
    for item in coord_node.text.split():
        parts = item.split(',')
        if len(parts) < 2:
            raise ValueError('Malformed KML coordinate tuple')
        lon, lat = float(parts[0]), float(parts[1])
        if not (isfinite(lon) and isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError('Invalid latitude/longitude in KML')
        result.append((lon, lat))
        if len(result) > MAX_VERTICES:
            raise ValueError('KML geometry contains too many vertices')
    return result


def _read_kml_geometry(element: Any):
    kind = _local_name(element.tag)
    if kind == 'Point':
        coords = _coordinates(element)
        if len(coords) != 1:
            raise ValueError('KML Point must contain one coordinate')
        return Point(coords[0])
    if kind == 'LineString':
        coords = _coordinates(element)
        if len(coords) < 2:
            raise ValueError('KML LineString needs at least two coordinates')
        return LineString(coords)
    if kind == 'Polygon':
        outer = _first_child(element, 'outerBoundaryIs')
        if outer is None:
            raise ValueError('KML Polygon missing outer boundary')
        outer_coords = _coordinates(outer)
        inner_coords = [_coordinates(inside) for inside in _children(element, 'innerBoundaryIs')]
        if len(outer_coords) < 3:
            raise ValueError('KML Polygon requires at least three coordinates')
        if any(len(hole) < 3 for hole in inner_coords):
            raise ValueError('KML Polygon contains malformed hole')
        return Polygon(outer_coords, inner_coords)
    if kind == 'MultiGeometry':
        geometries = [
            g for child in element
            if (g := _read_kml_geometry(child)) is not None
        ]
        if not geometries:
            return GeometryCollection()
        if all(g.geom_type == 'Polygon' for g in geometries):
            return MultiPolygon(geometries)
        if all(g.geom_type == 'LineString' for g in geometries):
            return MultiLineString(geometries)
        if all(g.geom_type == 'Point' for g in geometries):
            return MultiPoint(geometries)
        return GeometryCollection(geometries)
    return None


def _kml_properties(placemark: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ('name', 'description'):
        val = _first_text(placemark, key)
        if val:
            result[key] = val
    for item in _descendants(placemark, 'Data'):
        key = item.get('name')
        val = _first_text(item, 'value')
        if key and val is not None:
            result[key] = val
    for item in _descendants(placemark, 'SimpleData'):
        key = item.get('name')
        if key and item.text:
            result[key] = item.text.strip()
    return result


def _parse_kml(data: bytes) -> tuple[list[RawFeature], str]:
    try:
        root = SafeET.fromstring(data)
    except Exception as exc:
        raise InvalidGeospatialUpload(f'Invalid or unsafe KML XML: {exc}') from exc
    if _local_name(root.tag) != 'kml':
        raise InvalidGeospatialUpload('XML document is not a KML file')
    placemarks = _descendants(root, 'Placemark')
    if len(placemarks) > MAX_FEATURES:
        raise InvalidGeospatialUpload('KML exceeds maximum feature count')
    if not placemarks:
        raise InvalidGeospatialUpload('KML contains no Placemarks')
    raw: list[RawFeature] = []
    for i, placemark in enumerate(placemarks):
        geometry = None
        error = None
        for node in placemark:
            if _local_name(node.tag) in ('Point','LineString','Polygon','MultiGeometry'):
                try:
                    geometry = _read_kml_geometry(node)
                except (ValueError, TypeError, OverflowError) as exc:
                    error = str(exc)
                break
        props = _kml_properties(placemark)
        if error:
            props['_parse_error'] = error
        elif geometry is None:
            props['_parse_error'] = 'No supported KML geometry found'
        raw.append(RawFeature(str(placemark.get('id') or i + 1), geometry, props, CRS.from_epsg(4326)))
    return raw, 'EPSG:4326'


def _safe_zip_entries(zf: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries: dict[str, zipfile.ZipInfo] = {}
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_FILES:
        raise InvalidGeospatialUpload('ZIP contains too many entries')
    total = 0
    for info in infos:
        normalized = info.filename.replace('\\', '/')
        name = PurePosixPath(normalized)
        if normalized.startswith('/') or name.is_absolute() or '..' in name.parts or re.match(r'^[a-zA-Z]:', normalized):
            raise InvalidGeospatialUpload('ZIP contains an unsafe filename')
        unix_type = (info.external_attr >> 16) & 0o170000
        if unix_type == 0o120000:
            raise InvalidGeospatialUpload('ZIP contains a symbolic link')
        if info.is_dir():
            continue
        total += info.file_size
        if info.file_size > MAX_EXPANDED_BYTES or total > MAX_EXPANDED_BYTES:
            raise InvalidGeospatialUpload('ZIP uncompressed size exceeds limit')
        if info.compress_size and info.file_size > 200 * info.compress_size and info.file_size > 1024 * 1024:
            raise InvalidGeospatialUpload('Suspicious ZIP compression ratio')
        if normalized.casefold() in entries:
            raise InvalidGeospatialUpload('ZIP contains duplicate paths')
        entries[normalized.casefold()] = info
    return entries


def _parse_shapefile_zip(data: bytes) -> tuple[list[RawFeature], str | None]:
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except (OSError, zipfile.BadZipFile) as exc:
        raise InvalidGeospatialUpload('Not a valid ZIP archive') from exc
    with zf:
        entries = _safe_zip_entries(zf)
        shps = [key for key in entries if key.endswith('.shp') and not key.rsplit('/', 1)[-1].startswith('._')]
        if len(shps) != 1:
            raise InvalidGeospatialUpload('ZIP must contain exactly one .shp dataset')
        stem = shps[0][:-4]
        for ext in ('.shp', '.shx', '.dbf'):
            if stem + ext not in entries:
                raise InvalidGeospatialUpload(f'Shapefile ZIP missing {ext} component')
        try:
            files = {ext: zf.read(entries[stem+ext]) for ext in ('.shp','.shx','.dbf')}
        except (OSError, RuntimeError, zipfile.BadZipFile, ValueError) as exc:
            raise InvalidGeospatialUpload(f'Could not read ZIP contents: {exc}') from exc
        crs = None
        crs_label = None
        if stem + '.prj' in entries:
            try:
                crs = CRS.from_wkt(zf.read(entries[stem + '.prj']).decode('utf-8-sig'))
                crs_label = crs.to_string()
            except Exception as exc:
                raise InvalidGeospatialUpload('Cannot parse Shapefile .prj CRS') from exc
        cpg = 'utf-8'
        if stem + '.cpg' in entries:
            try:
                cpg = zf.read(entries[stem+'.cpg']).decode('ascii').strip() or 'utf-8'
            except UnicodeError:
                raise InvalidGeospatialUpload('Invalid Shapefile .cpg encoding')
        try:
            reader = shapefile.Reader(shp=BytesIO(files['.shp']), shx=BytesIO(files['.shx']), dbf=BytesIO(files['.dbf']), encoding=cpg, encodingErrors='replace')
            count = len(reader)
            if count > MAX_FEATURES:
                raise InvalidGeospatialUpload('Shapefile exceeds maximum feature count')
            raw: list[RawFeature] = []
            for index, shape_record in enumerate(reader.iterShapeRecords()):
                props = dict(shape_record.record.as_dict())
                props = {key: _json_safe(value) for key, value in props.items()}
                geom = None
                try:
                    if shape_record.shape.shapeType != shapefile.NULL:
                        geo = shape_record.shape.__geo_interface__
                        geom = shape(geo)
                except Exception as exc:
                    props['_parse_error'] = f'Invalid Shapefile feature: {exc}'
                raw.append(RawFeature(str(index+1), geom, props, crs))
            reader.close()
        except InvalidGeospatialUpload:
            raise
        except Exception as exc:
            raise InvalidGeospatialUpload(f'Could not read Shapefile: {exc}') from exc
    return raw, crs_label


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _vertex_count(g: Any) -> int:
    kind = g.geom_type
    if kind == 'Point':
        return 1
    if kind in ('LineString', 'LinearRing'):
        return len(g.coords)
    if kind == 'Polygon':
        return len(g.exterior.coords) + sum(len(h.coords) for h in g.interiors)
    if hasattr(g, 'geoms'):
        return sum(_vertex_count(x) for x in g.geoms)
    return 0


def _select_metric_crs(geom_wgs84: Any, geometry_type: str) -> tuple[CRS, str, list[str]]:
    """Use local UTM where suitable; otherwise local equal-area / equidistant projection."""
    centre = geom_wgs84.representative_point()
    lon, lat = centre.x, centre.y
    minlon, minlat, maxlon, maxlat = geom_wgs84.bounds
    warnings: list[str] = []
    if abs(maxlon-minlon) <= 5 and -79 <= minlat <= maxlat <= 83:
        zone = min(60, max(1, int((lon + 180) / 6) + 1))
        epsg = (32600 if lat >= 0 else 32700) + zone
        target = CRS.from_epsg(epsg)
        return target, target.to_string(), warnings
    # For large features one UTM zone can distort results. Select a local
    # equal-area or equidistant projection, and expose the caveat.
    warnings.append('Large or polar extent: locally centred projection; assess distortion for very large datasets')
    if geometry_type in ('Polygon','MultiPolygon'):
        proj = f'+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +type=crs'
    else:
        proj = f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +type=crs'
    target = CRS.from_user_input(proj)
    return target, proj, warnings


def _feature_result(raw: RawFeature, index: int) -> dict[str, Any]:
    geom = raw.geometry
    result: dict[str, Any] = {
        'id': raw.id, 'index': index, 'geometry_type': geom.geom_type if geom is not None else 'Unknown',
        'crs': raw.source_crs.to_string() if raw.source_crs else None,
        'properties': raw.properties, 'geometry': None, 'measurement': None,
        'measurement_crs': None, 'status': 'UNSUPPORTED', 'error': None, 'warnings': [],
    }
    if geom is None:
        result['status'] = 'FAILED'
        result['error'] = raw.properties.get('_parse_error', 'Missing or unreadable geometry')
        return result
    if geom.is_empty:
        result['status'] = 'FAILED'
        result['error'] = 'Empty geometry'
        return result
    if _vertex_count(geom) > MAX_VERTICES:
        result['status'] = 'FAILED'
        result['error'] = 'Feature exceeds vertex limit'
        return result
    if not geom.is_valid:
        result['status'] = 'FAILED'
        result['error'] = 'Invalid geometry: ' + (explain_validity(geom))
        return result
    if raw.source_crs is None:
        result['status'] = 'FAILED'
        result['error'] = 'Source CRS unknown: supply a valid .prj; measurements cannot be calculated safely'
        return result
    try:
        to_wgs = Transformer.from_crs(raw.source_crs, CRS.from_epsg(4326), always_xy=True)
        display = transform_geometry(to_wgs.transform, geom)
        if display.is_empty or not all(isfinite(v) for v in display.bounds):
            raise ValueError('Coordinates cannot be transformed to geographic CRS')
        # Longitude/latitude validity is NOT implied by a valid Shapely
        # geometry.  EPSG:4326 Shapefiles can contain longitude 181 or
        # latitude 95, and a same-CRS transform can silently retain them.
        min_lon, min_lat, max_lon, max_lat = display.bounds
        if min_lon < -180 or max_lon > 180 or min_lat < -90 or max_lat > 90:
            raise ValueError('Invalid longitude/latitude after CRS transformation')
        result['geometry'] = mapping(display)
        if geom.geom_type in ('Point', 'MultiPoint'):
            result['status'] = 'NOT_APPLICABLE'
            return result
        if geom.geom_type not in ('Polygon','MultiPolygon','LineString','MultiLineString'):
            result['status'] = 'UNSUPPORTED'
            result['error'] = f'No measurement defined for {geom.geom_type}'
            return result
        metric_crs, label, warnings = _select_metric_crs(display, geom.geom_type)
        transformer = Transformer.from_crs(raw.source_crs, metric_crs, always_xy=True)
        measured = transform_geometry(transformer.transform, geom)
        value = measured.area if geom.geom_type in ('Polygon','MultiPolygon') else measured.length
        if not isfinite(value):
            raise ValueError('Nonfinite geometry measurement')
        result['measurement'] = {
            'type': 'area' if geom.geom_type in ('Polygon','MultiPolygon') else 'length',
            'value': round(float(value), 6),
            'unit': 'm2' if geom.geom_type in ('Polygon','MultiPolygon') else 'm',
        }
        result['measurement_crs'] = label
        result['warnings'] = warnings
        result['status'] = 'MEASURED'
    except Exception as exc:
        result['status'] = 'FAILED'
        result['error'] = f'CRS/measurement error: {exc}'
    return result


def process_upload(filename: str, content: bytes) -> dict[str, Any]:
    """Parse and measure a KML or zipped Shapefile in memory.

    Returns structured JSON-compatible data. Upload failures raise
    InvalidGeospatialUpload; individual feature problems remain in results.
    """
    if not isinstance(content, bytes):
        raise InvalidGeospatialUpload('Upload content must be bytes')
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise InvalidGeospatialUpload(f'File must be 1 to {MAX_UPLOAD_BYTES} bytes')
    safe_name = filename.replace('\\', '/').split('/')[-1]
    if safe_name.lower().endswith('.kml'):
        raw, source_crs = _parse_kml(content)
    elif safe_name.lower().endswith('.zip'):
        raw, source_crs = _parse_shapefile_zip(content)
    else:
        raise InvalidGeospatialUpload('Accepted types: .kml or zipped Shapefile (.zip)')
    if len(raw) > MAX_FEATURES:
        raise InvalidGeospatialUpload('File exceeds feature-count limit')
    features = [_feature_result(x, i) for i, x in enumerate(raw)]
    return {
        'filename': safe_name,
        'source_crs': source_crs,
        'feature_count': len(features),
        'status': 'COMPLETED_WITH_ERRORS' if any(f['status'] == 'FAILED' for f in features) else 'COMPLETED',
        'successful_measurements': sum(f['status'] == 'MEASURED' for f in features),
        'failed_features': sum(f['status'] == 'FAILED' for f in features),
        'features': features,
    }

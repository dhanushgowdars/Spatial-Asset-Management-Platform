"""Bounded, deterministic 2D vector analysis of persisted GeoInsight survey results.

All supplied geometry is the *validated WGS84 display geometry* created by the
existing upload engine. Overlay, distance and area calculations occur only in
one shared projected metric CRS. No geodesic, raster or volumetric claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely import get_num_coordinates
from shapely.ops import transform, unary_union


MAX_ANALYSIS_FEATURES = 250
MAX_ANALYSIS_COORDINATES = 30_000
MAX_TOPOLOGY_POLYGONS = 120
MAX_ROUTE_GEOMETRIES = 120
MAX_RESULT_FEATURES = 150
MAX_STUDY_DIAGONAL_M = 250_000


class AnalysisValidationError(ValueError):
    """An actionable 422 response rather than a 500 for unsupported analysis."""


@dataclass
class PreparedDataset:
    name: str
    polygons: list[tuple[str, Any]]
    lines: list[tuple[str, Any]]
    excluded: list[dict[str, str]]


def _extract(data: dict[str, Any]) -> PreparedDataset:
    features = data.get('features', [])
    if not isinstance(features, list) or len(features) > MAX_ANALYSIS_FEATURES:
        raise AnalysisValidationError(f'Analysis supports at most {MAX_ANALYSIS_FEATURES} features per file')
    polygons: list[tuple[str, Any]] = []
    lines: list[tuple[str, Any]] = []
    excluded: list[dict[str, str]] = []
    coordinate_total = 0
    for f in features:
        kind = f.get('geometry_type')
        if kind not in ('Polygon', 'MultiPolygon', 'LineString', 'MultiLineString'):
            # A legitimate Point is not an analysis failure; unknown failed
            # geometries are called out instead of being silently ignored.
            if f.get('status') == 'FAILED':
                excluded.append({'feature_id': str(f.get('id')), 'reason': str(f.get('error') or 'Unknown geometry')[:240]})
            continue
        if f.get('status') != 'MEASURED' or not f.get('geometry'):
            excluded.append({'feature_id': str(f.get('id')), 'reason': str(f.get('error') or f.get('status'))[:240]})
            continue
        try:
            geom = shape(f['geometry'])
        except (TypeError, ValueError, KeyError) as exc:
            raise AnalysisValidationError(f'Feature {f.get("id")} has unreadable stored geometry') from exc
        if geom.is_empty or not geom.is_valid or geom.geom_type != kind:
            raise AnalysisValidationError(f'Feature {f.get("id")} has invalid stored geometry')
        if not geom.bounds or not all(isfinite(x) for x in geom.bounds):
            raise AnalysisValidationError(f'Feature {f.get("id")} has invalid bounds')
        coordinate_total += get_num_coordinates(geom)
        if coordinate_total > MAX_ANALYSIS_COORDINATES:
            raise AnalysisValidationError(f'Analysis exceeds {MAX_ANALYSIS_COORDINATES} input coordinates per dataset')
        (polygons if kind.endswith('Polygon') else lines).append((str(f.get('id')), geom))
    return PreparedDataset(str(data.get('filename') or 'Unnamed dataset'), polygons, lines, excluded)


def _common_projection(geometries: list[Any]) -> tuple[CRS, str, list[str]]:
    if not geometries:
        raise AnalysisValidationError('No measurable geometries were found for this analysis')
    west = min(g.bounds[0] for g in geometries)
    south = min(g.bounds[1] for g in geometries)
    east = max(g.bounds[2] for g in geometries)
    north = max(g.bounds[3] for g in geometries)
    if not all(isfinite(v) for v in (west, south, east, north)) or west < -180 or east > 180 or south < -90 or north > 90:
        raise AnalysisValidationError('Invalid WGS84 longitude/latitude bounds')
    if east-west > 5 or north-south > 5 or south < -79 or north > 83:
        raise AnalysisValidationError('Survey extents exceed the supported local UTM study area (5 degrees each axis, nonpolar, no dateline crossings)')
    lon = (west+east) / 2
    lat = (south+north) / 2
    zone = min(60, max(1, int((lon+180) / 6) + 1))
    crs = CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)
    forward = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
    corners = [forward.transform(x, y) for x in (west,east) for y in (south,north)]
    if not all(isfinite(v) for point in corners for v in point):
        raise AnalysisValidationError('Unable to project analysis bounds')
    width = max(x for x, _ in corners) - min(x for x, _ in corners)
    height = max(y for _, y in corners) - min(y for _, y in corners)
    if hypot(width,height) > MAX_STUDY_DIAGONAL_M:
        raise AnalysisValidationError('Study area diagonal exceeds 250 km; split into smaller local surveys to limit planar distortion')
    notes = ['Measurements use one common local UTM projected CRS; not a cadastral or geodesic accuracy guarantee.']
    if width > 100_000 or height > 100_000:
        notes.append('Large local extent: assess projection distortion before engineering use.')
    return crs, crs.to_string(), notes


def _project_list(items: list[tuple[str, Any]], projection: CRS) -> list[tuple[str, Any]]:
    forward = Transformer.from_crs('EPSG:4326', projection, always_xy=True)
    result = []
    for key, geom in items:
        converted = transform(forward.transform, geom)
        if converted.is_empty or not converted.is_valid or not all(isfinite(v) for v in converted.bounds):
            raise AnalysisValidationError(f'Feature {key} cannot be safely projected for analysis')
        result.append((key, converted))
    return result


# GEOINSIGHT_DERIVED_PROVENANCE_V1: derived results carry the same
# calculation metadata as their parent analysis response.
DERIVED_OPERATIONS = {
    'added': 'Current footprint minus baseline footprint',
    'removed': 'Baseline footprint minus current footprint',
    'unchanged_overlap': 'Intersection of baseline and current footprints',
    'overlap_area': 'Intersection of two survey parcels',
    'uncovered_within_reference': 'Reference boundary minus surveyed footprint',
    'outside_reference': 'Surveyed footprint minus reference boundary',
}


def _region_geojson(regions: list[tuple[str, Any]], projection: CRS, *, method: str) -> dict[str, Any]:
    inverse = Transformer.from_crs(projection, 'EPSG:4326', always_xy=True)
    collection = []
    for label, geom in regions:
        if geom.is_empty:
            continue
        if len(collection) >= MAX_RESULT_FEATURES:
            raise AnalysisValidationError('Analysis result exceeds maximum output geometry count')
        display = transform(inverse.transform, geom)
        if display.is_empty or not all(isfinite(v) for v in display.bounds):
            raise AnalysisValidationError('Could not transform analysis result to WGS84')
        collection.append({'type':'Feature', 'properties': {
            'category':label, 'area_m2': round(geom.area, 6),
            '_status':'CALCULATED',
            '_measurement_crs':projection.to_string(),
            '_measurement_method':method,
            '_operation':DERIVED_OPERATIONS.get(label, 'Projected geometry overlay'),
        }, 'geometry': mapping(display)})
    return {'type':'FeatureCollection', 'features':collection}


def _metric(value: float) -> float:
    if not isfinite(value) or value < -1e-5:
        raise AnalysisValidationError('Nonfinite or negative analysis metric')
    return round(max(0.0, float(value)), 6)


def compare_surveys(baseline_data: dict[str, Any], current_data: dict[str, Any], *, baseline_id: str, current_id: str) -> dict[str, Any]:
    """Set-theoretic added/removed/overlap calculations of polygon footprints."""
    baseline = _extract(baseline_data)
    current = _extract(current_data)
    if not baseline.polygons or not current.polygons:
        raise AnalysisValidationError('Both datasets must have at least one successfully measured polygon')
    projection, label, notes = _common_projection([g for _,g in baseline.polygons+current.polygons])
    try:
        old = unary_union([g for _,g in _project_list(baseline.polygons,projection)])
        new = unary_union([g for _,g in _project_list(current.polygons,projection)])
        if old.is_empty or new.is_empty or not old.is_valid or not new.is_valid:
            raise AnalysisValidationError('A survey footprint has no valid polygon area')
        added = new.difference(old)
        removed = old.difference(new)
        overlap = old.intersection(new)
        baseline_area, current_area = old.area, new.area
        added_area, removed_area, overlap_area = added.area, removed.area, overlap.area
        union_area = old.union(new).area
    except AnalysisValidationError:
        raise
    except Exception as exc:
        raise AnalysisValidationError('Unable to overlay survey polygons; check topology and local extent') from exc
    excluded = {'baseline':baseline.excluded, 'current':current.excluded}
    partial = bool(baseline.excluded or current.excluded)
    if partial:
        notes.append('Partial analysis: unmeasured or invalid features were excluded; inspect excluded_features before using the totals.')
    return {
        'baseline_file_id':baseline_id, 'current_file_id':current_id,
        'baseline_filename':baseline.name, 'current_filename':current.name,
        'measurement_crs':label, 'method':'projected_planar_polygon_overlay',
        'partial':partial, 'excluded_features':excluded, 'warnings':notes,
        'metrics':{
            'baseline_area_m2':_metric(baseline_area), 'current_area_m2':_metric(current_area),
            'added_area_m2':_metric(added_area), 'removed_area_m2':_metric(removed_area),
            'overlap_area_m2':_metric(overlap_area), 'union_area_m2':_metric(union_area),
            'net_change_m2':round(current_area-baseline_area,6),
            'overlap_pct_of_baseline':round(100*overlap_area/baseline_area,4) if baseline_area else 0,
            'overlap_pct_of_current':round(100*overlap_area/current_area,4) if current_area else 0,
            'intersection_over_union_pct':round(100*overlap_area/union_area,4) if union_area else 0,
        },
        'change_geojson':_region_geojson([('added',added),('removed',removed),('unchanged_overlap',overlap)],projection,method='projected_planar_polygon_overlay'),
    }


def topology_report(data: dict[str, Any], *, file_id: str, reference_data: dict[str, Any] | None = None, reference_id: str | None = None) -> dict[str, Any]:
    """Report real polygon overlaps; gaps only against an explicit reference boundary."""
    survey = _extract(data)
    if not survey.polygons:
        raise AnalysisValidationError('File contains no successfully measured polygons')
    if len(survey.polygons) > MAX_TOPOLOGY_POLYGONS:
        raise AnalysisValidationError(f'Topology supports at most {MAX_TOPOLOGY_POLYGONS} polygons')
    reference = _extract(reference_data) if reference_data is not None else None
    if reference is not None and not reference.polygons:
        raise AnalysisValidationError('Reference file contains no measurable polygon boundary')
    all_polys = survey.polygons+(reference.polygons if reference else [])
    projection, label, warnings = _common_projection([g for _,g in all_polys])
    survey_polygons = _project_list(survey.polygons,projection)
    issues, actual_overlap_count = [], 0
    shapes = []
    max_pair_detail = MAX_RESULT_FEATURES - (2 if reference else 0)
    try:
        for i,(fid,poly) in enumerate(survey_polygons):
            for other_id,other in survey_polygons[i+1:]:
                # Avoid expensive GEOS overlay unless projected bounds intersect.
                a,b,c,d = poly.bounds
                e,f,g,h = other.bounds
                if c<=e or g<=a or d<=f or h<=b:
                    continue
                shared = poly.intersection(other)
                if shared.area <= 1e-6:
                    continue
                actual_overlap_count += 1
                if len(issues) < max_pair_detail:
                    issues.append({'code':'POLYGON_OVERLAP','severity':'WARNING',
                        'feature_a':fid,'feature_b':other_id,'overlap_area_m2':_metric(shared.area)})
                    shapes.append(('overlap_area', shared))
        boundary_report = None
        if reference:
            refgeom = unary_union([p for _,p in _project_list(reference.polygons,projection)])
            surveyed = unary_union([p for _,p in survey_polygons])
            uncovered = refgeom.difference(surveyed)
            outside = surveyed.difference(refgeom)
            boundary_report = {'reference_file_id':reference_id,
                'uncovered_area_m2':_metric(uncovered.area), 'outside_reference_area_m2':_metric(outside.area)}
            shapes.extend([('uncovered_within_reference',uncovered),('outside_reference',outside)])
    except AnalysisValidationError:
        raise
    except Exception as exc:
        raise AnalysisValidationError('Topology operation failed; check input polygon validity') from exc
    exclusions = survey.excluded+(reference.excluded if reference else [])
    if exclusions:
        warnings.append('Partial analysis: invalid features are excluded from topology calculations.')
    return {'file_id':file_id, 'reference_file_id':reference_id, 'measurement_crs':label,
            'method':'projected_planar_topology','partial':bool(exclusions), 'excluded_features':exclusions,
            'warnings':warnings, 'overlap_pair_count':actual_overlap_count,
            'overlap_issues':issues, 'issues_truncated':actual_overlap_count>len(issues),
            'gaps_evaluated':reference is not None, 'boundary_comparison':boundary_report,
            'geojson':_region_geojson(shapes,projection,method='projected_planar_topology')}


def route_zone_report(route_data:dict[str,Any], zone_data:dict[str,Any], *, route_id:str, zone_id:str) -> dict[str,Any]:
    """Calculate line length inside polygons, avoiding double counting in route totals."""
    routes, zones = _extract(route_data),_extract(zone_data)
    if not routes.lines or not zones.polygons:
        raise AnalysisValidationError('Provide at least one measured LineString route and one measured Polygon zone')
    if len(routes.lines)>MAX_ROUTE_GEOMETRIES or len(zones.polygons)>MAX_ROUTE_GEOMETRIES:
        raise AnalysisValidationError(f'Route/zone analysis supports at most {MAX_ROUTE_GEOMETRIES} routes or zones')
    projection,label,warnings = _common_projection([g for _,g in routes.lines+zones.polygons])
    measured_routes = _project_list(routes.lines,projection)
    measured_zones = _project_list(zones.polygons,projection)
    inside = []
    route_results = []
    try:
        zone_union = unary_union([g for _,g in measured_zones])
        for line_id,line in measured_routes:
            total_inside = line.intersection(zone_union)
            entry = {'route_feature_id':line_id,'length_m':_metric(line.length),
                     'inside_any_zone_m':_metric(total_inside.length),
                     'outside_all_zones_m':_metric(line.difference(zone_union).length),
                     'zone_intersections':[]}
            for polygon_id,zone in measured_zones:
                clipped = line.intersection(zone)
                if clipped.length <= 1e-6:
                    continue
                entry['zone_intersections'].append({'zone_feature_id':polygon_id,'length_inside_m':_metric(clipped.length)})
                inside.append((line_id, polygon_id, clipped))
                if len(inside) > MAX_RESULT_FEATURES:
                    raise AnalysisValidationError('Too many route/zone intersections to return; split input datasets')
            route_results.append(entry)
    except AnalysisValidationError:
        raise
    except Exception as exc:
        raise AnalysisValidationError('Unable to intersect route lines with survey zones') from exc
    if routes.excluded or zones.excluded:
        warnings.append('Partial analysis: invalid input features are excluded from routes or zones.')
    reverse = Transformer.from_crs(projection,'EPSG:4326',always_xy=True)
    features = [{'type':'Feature','properties':{'route_feature_id':line_id,
               'zone_feature_id':polygon_id, 'length_m':_metric(line.length),
               '_status':'CALCULATED', '_measurement_crs':label,
               '_measurement_method':'projected_planar_line_polygon_overlay',
               '_operation':'Route intersection with selected zone'},
               'geometry':mapping(transform(reverse.transform,line))} for line_id,polygon_id,line in inside]
    return {'route_file_id':route_id,'zone_file_id':zone_id,'measurement_crs':label,
            'method':'projected_planar_line_polygon_overlay', 'warnings':warnings,
            'partial':bool(routes.excluded or zones.excluded),
            'excluded_features':{'routes':routes.excluded,'zones':zones.excluded},
            'summary':{'route_count':len(measured_routes),'zone_count':len(measured_zones),
                'routes_crossing_zones':sum(bool(x['zone_intersections']) for x in route_results),
                'total_length_inside_any_zone_m':_metric(sum(x['inside_any_zone_m'] for x in route_results)),
                'note':'Per-zone lengths may overlap. Union-of-zones totals count each route section once.'},
            'routes':route_results, 'intersection_geojson':{'type':'FeatureCollection','features':features}}

"""Deterministic GIS benchmark fixtures with independent projected-metric oracles.

All coordinate construction starts in EPSG:32643 (metres) then converts to
RFC 7946 WGS84 for GeoJSON/KML. A measurement oracle is calculated BEFORE
transformation using original Shapely geometries, not the GeoInsight engine.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from math import cos, sin, pi
import json
import math
import zipfile

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon, LineString, MultiPolygon, mapping
from shapely.ops import transform

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
FIXTURES = OUT / "fixtures"
MANIFEST = OUT / "fixture_manifest.json"
READ_TARGETS = OUT / "read_targets.json"
BASE_X, BASE_Y = 500_000.0, 1_400_000.0
TO_WGS = Transformer.from_crs(32643, 4326, always_xy=True)


def to_geo(geometry):
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("Generator produced an invalid geometry")
    value = transform(TO_WGS.transform, geometry)
    if value.is_empty or not value.is_valid:
        raise ValueError("Invalid result after WGS84 transformation")
    return mapping(value)


def square(x, y, size=100.0):
    return Polygon(((x, y), (x + size, y), (x + size, y + size),
                    (x, y + size), (x, y)))


def feature(fid, geom, kind):
    result = {"type": "Feature", "id": fid,
              "properties": {"source": "SYNTHETIC_BENCHMARK", "kind": kind,
                             "survey_id": fid, "zone": "UTM43N"},
              "geometry": to_geo(geom)}
    metric_type = "area" if geom.geom_type.endswith("Polygon") else (
        "length" if geom.geom_type.endswith("LineString") else None)
    expected = {"id": fid, "geometry_type": geom.geom_type,
                "status": "MEASURED" if metric_type else "NOT_APPLICABLE"}
    if metric_type:
        expected.update({"measurement_type": metric_type,
                         "value": round(geom.area if metric_type == "area" else geom.length, 6),
                         "unit": "m2" if metric_type == "area" else "m"})
    return result, expected


def make_grid(name, n):
    polygons = int(n * 0.8)
    features, oracles = [], []
    columns = int(math.ceil(math.sqrt(n)))
    for i in range(n):
        x = BASE_X + (i % columns) * 150.0
        y = BASE_Y + (i // columns) * 150.0
        if i < polygons:
            geom = square(x, y)
        else:
            geom = LineString(((x, y), (x + 120.0, y)))
        f, o = feature(f"{name}-{i:05d}", geom, "parcel" if i < polygons else "route")
        features.append(f); oracles.append(o)
    return features, oracles


def complex_geometries():
    out, oracle = [], []
    for i in range(80):
        x = BASE_X + (i % 10) * 320.0
        y = BASE_Y + (i // 10) * 320.0
        if i < 20:
            exterior = Point(x + 125, y + 125).buffer(95, quad_segs=150)
            hole = Point(x + 125, y + 125).buffer(25, quad_segs=50)
            geom = Polygon(exterior.exterior.coords, [hole.exterior.coords])
            kind = "polygon_with_hole"
        elif i < 40:
            geom = MultiPolygon((Point(x + 85, y + 85).buffer(52, quad_segs=65),
                                 Point(x + 215, y + 215).buffer(42, quad_segs=65)))
            kind = "multipart_polygon"
        else:
            pts = [(x + t, y + 130.0 + 23.0 * sin(2*pi*t/120.0))
                   for t in range(151)]
            geom = LineString(pts)
            kind = "curved_line"
        f, o = feature(f"complex-{i:03d}", geom, kind)
        out.append(f); oracle.append(o)
    return out, oracle


def geojson_bytes(features):
    return json.dumps({"type":"FeatureCollection", "features":features},
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fmt_pair(pair):
    return f"{pair[0]:.10f},{pair[1]:.10f}"


def make_kml(n=150):
    chunks = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
    oracles = []
    for i in range(n):
        x = BASE_X + (i % 15)*165.0
        y = BASE_Y + (i // 15)*165.0
        if i < 100:
            geom = square(x,y)
            coords = " ".join(fmt_pair(TO_WGS.transform(*p)) for p in geom.exterior.coords)
            body = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            kind = "parcel"
        elif i < 125:
            geom = LineString([(x,y),(x+120,y)])
            coords = " ".join(fmt_pair(TO_WGS.transform(*p)) for p in geom.coords)
            body = f"<LineString><coordinates>{coords}</coordinates></LineString>"
            kind = "route"
        else:
            geom = Point(x,y)
            body = f"<Point><coordinates>{fmt_pair(TO_WGS.transform(x,y))}</coordinates></Point>"
            kind = "inspection"
        fid = f"kml-{i:03d}"
        chunks.append(f'<Placemark id="{fid}"><name>{kind}-{i}</name>{body}</Placemark>')
        oracle = {"id":fid, "geometry_type":geom.geom_type,
                  "status":"NOT_APPLICABLE" if kind == "inspection" else "MEASURED"}
        if kind != "inspection":
            value = geom.area if kind == "parcel" else geom.length
            oracle.update({"measurement_type":"area" if kind == "parcel" else "length",
                           "value":round(value, 6), "unit":"m2" if kind=="parcel" else "m"})
        oracles.append(oracle)
    chunks.append('</Document></kml>')
    return "".join(chunks).encode("utf-8"),oracles


def make_zip_shapefile(n=250, include_prj=True):
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("SURVEY_ID", "C", 32)
    writer.field("AREA_M2", "N", 12, 2)
    oracles = []
    columns = int(math.ceil(math.sqrt(n)))
    for i in range(n):
        x = BASE_X + (i % columns) * 160.0
        y = BASE_Y + (i // columns) * 160.0
        geom = square(x,y)
        # Correct clockwise Shapefile outer rings, matching existing API tests.
        ring = list(geom.exterior.coords)[::-1]
        writer.poly([[[float(px),float(py)] for px,py in ring]])
        writer.record(f"plot-{i:04d}",10000)
        oracles.append({"id":str(i+1), "geometry_type":"Polygon", "status":"MEASURED",
                        "measurement_type":"area", "value":10000.0, "unit":"m2"})
    writer.close()
    target = BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ext, content in (("shp", shp), ("shx", shx), ("dbf", dbf)):
            zf.writestr("plots/bench."+ext, content.getvalue())
        if include_prj:
            zf.writestr("plots/bench.prj", CRS.from_epsg(32643).to_wkt())
    return target.getvalue(),oracles


def fixture_specs():
    med, med_oracles = make_grid("medium",250)
    large, large_oracles = make_grid("large",1200)
    complex_items, complex_oracles = complex_geometries()
    shp_bytes, shp_oracles = make_zip_shapefile()
    kml_bytes,kml_oracles = make_kml()
    kmz = BytesIO()
    with zipfile.ZipFile(kmz,"w",compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("survey/doc.kml",kml_bytes)
    return {
        "medium_geojson": ("medium_250.geojson",geojson_bytes(med),med_oracles,"EPSG:4326"),
        "large_geojson": ("large_1200.geojson",geojson_bytes(large),large_oracles,"EPSG:4326"),
        "complex_geojson": ("complex_80.geojson",geojson_bytes(complex_items),complex_oracles,"EPSG:4326"),
        "medium_shapefile": ("medium_250.zip",shp_bytes,shp_oracles,"EPSG:32643"),
        "medium_kml": ("medium_150.kml",kml_bytes,kml_oracles,"EPSG:4326"),
        "medium_kmz": ("medium_150.kmz",kmz.getvalue(),kml_oracles,"EPSG:4326"),
    }


def generate():
    FIXTURES.mkdir(parents=True,exist_ok=True)
    entries={}
    for key,(filename,content,oracles,crs) in fixture_specs().items():
        path = FIXTURES / filename
        path.write_bytes(content)
        entry={"filename":filename,"sha256":sha256(content).hexdigest(),
               "bytes":len(content),"feature_count":len(oracles),
               "successful_measurements":sum(o["status"]=="MEASURED" for o in oracles),
               "crs":crs, "expected_status":"COMPLETED",
               "samples": [oracles[i] for i in sorted({0, len(oracles)//3, 2*len(oracles)//3, len(oracles)-1})],
               "all_oracles": oracles,
               "type_counts":{g:sum(o["geometry_type"]==g for o in oracles)
                              for g in sorted({o["geometry_type"] for o in oracles})}}
        entries[key]=entry
    MANIFEST.write_text(json.dumps({"version":2, "source":"SYNTHETIC ONLY",
                                    "fixtures":entries},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return entries


def load_manifest():
    if not MANIFEST.is_file():
        raise RuntimeError("Missing fixture manifest. Run: python benchmarks/v2/prepare.py")
    obj=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if obj.get("version")!=2 or not isinstance(obj.get("fixtures"),dict):
        raise RuntimeError("Unexpected fixture manifest version")
    for key,entry in obj["fixtures"].items():
        content=(FIXTURES / entry["filename"]).read_bytes()
        if sha256(content).hexdigest()!=entry["sha256"]:
            raise RuntimeError(f"Changed benchmark fixture: {key}")
    return obj["fixtures"]


def verify_results(features, entry, *, full=False):
    """Validate independent geometry expectations; don't just test HTTP 200."""
    if not isinstance(features,list) or len(features)!=entry["feature_count"]:
        raise ValueError(f"Unexpected number of stored features: {len(features) if isinstance(features,list) else 'not list'}")
    statuses={"MEASURED":0,"NOT_APPLICABLE":0,"FAILED":0,"UNSUPPORTED":0}
    for f in features:
        status=f.get("status")
        if status in statuses:
            statuses[status]+=1
    if statuses["MEASURED"]!=entry["successful_measurements"]:
        raise ValueError(f"Measured count mismatch: {statuses}")
    if statuses["FAILED"] or statuses["UNSUPPORTED"]:
        raise ValueError(f"Unexpected invalid/unsupported features: {statuses}")
    by_id={str(f.get("id")):f for f in features}
    if len(by_id)!=len(features):
        raise ValueError("Duplicate feature ids")
    for expected in (entry["all_oracles"] if full else entry["samples"]):
        fid=expected["id"]
        f=by_id.get(fid)
        if not isinstance(f,dict) or f.get("geometry_type")!=expected["geometry_type"] or f.get("status")!=expected["status"]:
            raise ValueError(f"Incorrect geometry type or status for {fid}")
        if expected["status"]=="MEASURED":
            m=f.get("measurement") or {}
            if m.get("type")!=expected["measurement_type"] or m.get("unit")!=expected["unit"]:
                raise ValueError(f"Incorrect measurement semantics for {fid}")
            actual=m.get("value")
            if not isinstance(actual,(int,float)) or not math.isfinite(actual):
                raise ValueError(f"Missing/nonfinite measurement value for {fid}")
            expected_val=expected["value"]
            # Geodetic roundtrip can introduce tiny offsets; this bound rejects
            # unit conversions, area inflation and gross geometric mistakes.
            tolerance=max(0.25, abs(expected_val)*0.0002)
            if abs(actual-expected_val)>tolerance:
                raise ValueError(f"Wrong {fid}: expected {expected_val}, got {actual}, tol {tolerance}")
        elif f.get("measurement") is not None:
            raise ValueError(f"Point unexpectedly measured: {fid}")
    return statuses


def enforce_local_only(host):
    from urllib.parse import urlsplit
    addr=urlsplit(str(host).rstrip("/"))
    if (addr.scheme,addr.hostname,addr.port)!=("http","127.0.0.1",18130) or (addr.path not in ("", "/")) or addr.username or addr.password or addr.query or addr.fragment:
        raise RuntimeError("BLOCKED: benchmarks are restricted to http://127.0.0.1:18130")

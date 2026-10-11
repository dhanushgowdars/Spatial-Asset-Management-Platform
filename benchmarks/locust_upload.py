"""Local-only GeoInsight upload baseline: valid KML / zipped Shapefile.

Run from GeoInsight-Hardening-Lab with a DEDICATED local SQLite benchmark DB.
All clients must target http://127.0.0.1:18130. This is a mixed
upload-and-verification workload; each successful upload is followed by one
GET that verifies real stored geometry results. Report POST and GET separately.
"""
from __future__ import annotations

from io import BytesIO
from urllib.parse import urlsplit
import zipfile

import shapefile
from pyproj import CRS
from locust import HttpUser, between, task

KML = b'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark id="poly"><name>Benchmark Plot</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
76.5,12.0 76.51,12.0 76.51,12.01 76.5,12.01 76.5,12.0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark id="track"><name>Benchmark Track</name><LineString>
<coordinates>76.5,12.0 76.51,12.0</coordinates></LineString></Placemark>
<Placemark id="beacon"><name>Benchmark Beacon</name><Point>
<coordinates>76.5,12.0</coordinates></Point></Placemark>
</Document></kml>'''


def make_known_area_zip() -> bytes:
    """100 m x 100 m polygon in EPSG:32643; known area 10,000 m2."""
    shp, shx, dbf = BytesIO(), BytesIO(), BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("NAME", "C", 40)
    writer.poly([[
        [500000, 1400000],
        [500000, 1400100],
        [500100, 1400100],
        [500100, 1400000],
        [500000, 1400000],
    ]])
    writer.record("100x100 benchmark")
    writer.close()
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ext, stream in (("shp", shp), ("shx", shx), ("dbf", dbf)):
            zf.writestr(f"plot.{ext}", stream.getvalue())
        zf.writestr("plot.prj", CRS.from_epsg(32643).to_wkt())
    return out.getvalue()


SHP_ZIP = make_known_area_zip()


def enforce_local_only(base_url: str) -> None:
    url = urlsplit(base_url)
    if (url.scheme, url.hostname, url.port) != ("http", "127.0.0.1", 18130):
        raise RuntimeError(
            "BLOCKED: this workload is authorized only for "
            "http://127.0.0.1:18130. Do not run against Render or other sites."
        )


class GeoInsightUploadUser(HttpUser):
    """Controlled upload+verification workload; no reads of other user data."""

    host = "http://127.0.0.1:18130"
    wait_time = between(1.5, 3.5)

    def on_start(self) -> None:
        enforce_local_only(str(self.client.base_url))

    @task(3)
    def kml_upload(self) -> None:
        self.upload_and_verify(
            label="KML", filename="bench.kml", content=KML,
            mime="application/vnd.google-earth.kml+xml",
            expected_features=3, expected_measured=2, expected_crs="EPSG:4326",
        )

    @task(1)
    def shapefile_upload(self) -> None:
        self.upload_and_verify(
            label="Shapefile", filename="bench.zip", content=SHP_ZIP,
            mime="application/zip", expected_features=1,
            expected_measured=1, expected_crs="EPSG:32643",
        )

    def upload_and_verify(
        self, *, label: str, filename: str, content: bytes, mime: str,
        expected_features: int, expected_measured: int, expected_crs: str,
    ) -> None:
        file_id = None
        with self.client.post(
            "/api/files/", name=f"POST {label} upload", catch_response=True,
            files={"file": (filename, content, mime)}, timeout=30,
        ) as response:
            try:
                if response.status_code != 201:
                    raise ValueError(f"HTTP {response.status_code}: {response.text[:180]}")
                data = response.json()
                fid = data.get("id")
                if not isinstance(fid, str) or len(fid) != 32 or not all(c in "0123456789abcdef" for c in fid.lower()):
                    raise ValueError("Invalid upload ID")
                if data.get("feature_count") != expected_features:
                    raise ValueError("Unexpected feature count")
                if data.get("successful_measurements") != expected_measured:
                    raise ValueError("Unexpected successful measurement count")
                if data.get("status") != "COMPLETED":
                    raise ValueError("Upload not COMPLETED")
                if data.get("crs") != expected_crs:
                    raise ValueError("Unexpected source CRS")
                file_id = fid
            except (ValueError, TypeError, KeyError) as exc:
                response.failure(f"Upload validation failed: {exc}")

        if file_id is None:
            return

        with self.client.get(
            f"/api/files/{file_id}/measurements/",
            name=f"VERIFY {label} measurements", catch_response=True, timeout=20,
        ) as response:
            try:
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                data = response.json()
                features = data.get("measurements")
                if data.get("file_id") != file_id or not isinstance(features, list) or len(features) != expected_features:
                    raise ValueError("Uploaded file could not be retrieved correctly")
                if label == "Shapefile":
                    feat = features[0]
                    metric = feat.get("measurement") or {}
                    if not (feat.get("status") == "MEASURED"
                            and metric.get("type") == "area"
                            and metric.get("unit") == "m2"
                            and isinstance(metric.get("value"), (int, float))
                            and abs(metric["value"] - 10000.0) <= 0.05):
                        raise ValueError("Known 10,000 m2 geometry measurement is incorrect")
                else:
                    by_type = {f.get("geometry_type"): f for f in features}
                    polygon = by_type.get("Polygon") or {}
                    line = by_type.get("LineString") or {}
                    point = by_type.get("Point") or {}
                    if not (
                        polygon.get("status") == "MEASURED"
                        and (polygon.get("measurement") or {}).get("value", 0) > 1_000_000
                        and line.get("status") == "MEASURED"
                        and (line.get("measurement") or {}).get("value", 0) > 0
                        and point.get("status") == "NOT_APPLICABLE"
                        and point.get("measurement") is None
                    ):
                        raise ValueError("KML geometry results or point status incorrect")
            except (TypeError, ValueError, AttributeError) as exc:
                response.failure(f"Stored result verification failed: {exc}")

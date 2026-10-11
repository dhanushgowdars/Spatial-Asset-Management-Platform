"""GeoInsight V2 realistic benchmarking: separate upload and seeded-read profiles.

ALWAYS target the local benchmark-only server, not Render. Preflight before load.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from locust import HttpUser, between, task

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_lib import FIXTURES, READ_TARGETS, enforce_local_only, load_manifest, verify_results

ENTRIES=load_manifest()
CONTENT={k:(FIXTURES/e["filename"]).read_bytes() for k,e in ENTRIES.items()}


def mime_type(name):
    if name.endswith(".geojson"):return "application/geo+json"
    if name.endswith(".kml"):return "application/vnd.google-earth.kml+xml"
    if name.endswith(".kmz"):return "application/vnd.google-earth.kmz"
    return "application/zip"


class LocalUser(HttpUser):
    abstract=True
    host="http://127.0.0.1:18130"

    def on_start(self):
        enforce_local_only(self.client.base_url)

    def post_and_check(self, key):
        entry=ENTRIES[key]
        ident=None
        with self.client.post("/api/files/",name=f"POST [{key}]",catch_response=True,
                              files={"file":(entry["filename"],CONTENT[key],mime_type(entry["filename"]))},
                              timeout=120) as response:
            try:
                if response.status_code!=201:
                    raise ValueError(f"HTTP {response.status_code}: {response.text[:180]}")
                d=response.json()
                if d.get("status")!=entry["expected_status"] or d.get("feature_count")!=entry["feature_count"] or d.get("successful_measurements")!=entry["successful_measurements"] or d.get("sha256")!=entry["sha256"] or d.get("crs")!=entry["crs"]:
                    raise ValueError("Incorrect completed-upload metadata")
                ident=d.get("id")
                if not isinstance(ident,str) or len(ident)!=32 or not all(c in "0123456789abcdef" for c in ident):
                    raise ValueError("Malformed stored identifier")
            except (ValueError,TypeError,KeyError) as exc:
                response.failure(f"Upload validation: {exc}")
        if ident is None:return
        with self.client.get(f"/api/files/{ident}/measurements/",
                             name=f"VERIFY [{key}]",catch_response=True,timeout=120) as response:
            try:
                if response.status_code!=200:
                    raise ValueError(f"HTTP {response.status_code}")
                data=response.json()
                if data.get("file_id")!=ident or data.get("feature_count")!=entry["feature_count"]:
                    raise ValueError("Wrong stored file")
                verify_results(data.get("measurements"),entry)
            except (TypeError,ValueError,AttributeError,KeyError) as exc:
                response.failure(f"Measurement verification: {exc}")


class GeoInsightMediumUser(LocalUser):
    abstract=False
    """250 feature GeoJSON / Shapefile and 150 feature KML/KMZ uploads."""
    wait_time=between(0.6,1.4)

    @task(3)
    def geojson_medium(self):self.post_and_check("medium_geojson")

    @task(2)
    def shapefile_medium(self):self.post_and_check("medium_shapefile")

    @task(1)
    def kml_medium(self):self.post_and_check("medium_kml")

    @task(1)
    def kmz_medium(self):self.post_and_check("medium_kmz")


class GeoInsightLargeUser(LocalUser):
    abstract=False
    """1,200 measured features; heavy persistence and JSON transfer."""
    wait_time=between(1.5,3.0)

    @task
    def large_geojson(self):self.post_and_check("large_geojson")


class GeoInsightComplexUser(LocalUser):
    abstract=False
    """80 nontrivial geometries incl holes, multipart and vertex-dense lines."""
    wait_time=between(1.2,2.5)

    @task
    def complex_geojson(self):self.post_and_check("complex_geojson")


class GeoInsightSeededReadUser(LocalUser):
    abstract=False
    """No uploads during read benchmarks. Seed once with seed_reads.py."""
    wait_time=between(0.4,1.1)

    def on_start(self):
        super().on_start()
        if not READ_TARGETS.is_file():
            raise RuntimeError("Seed first: python benchmarks/v2/seed_reads.py")
        obj=json.loads(READ_TARGETS.read_text(encoding="utf-8"))
        enforce_local_only(obj.get("server"))
        self.targets=obj.get("targets")
        if not isinstance(self.targets,dict) or any(
            k not in self.targets or self.targets[k].get("sha256")!=e["sha256"]
            for k,e in ENTRIES.items()
        ):
            raise RuntimeError("Stale read targets or fixture hashes; rerun seed_reads.py")

    def read(self,key,route):
        entry=ENTRIES[key]
        fid=self.targets[key]["id"]
        with self.client.get(f"/api/files/{fid}/{route}",name=f"GET [{key}] {route}",
                             catch_response=True,timeout=120) as response:
            try:
                if response.status_code!=200:raise ValueError(f"HTTP {response.status_code}")
                data=response.json()
                if route=="measurements/":
                    if data.get("file_id")!=fid or data.get("feature_count")!=entry["feature_count"]:
                        raise ValueError("Wrong measurements payload")
                    verify_results(data.get("measurements"),entry)
                elif route=="summary/":
                    if data.get("file_id")!=fid or data.get("feature_count")!=entry["feature_count"] or data.get("counts",{}).get("measured")!=entry["successful_measurements"]:
                        raise ValueError("Wrong summary")
                elif route=="quality/":
                    summ=data.get("summary",{})
                    if data.get("file_id")!=fid or summ.get("total_features")!=entry["feature_count"] or summ.get("measured")!=entry["successful_measurements"] or summ.get("error_features")!=0:
                        raise ValueError("Wrong quality report")
            except (ValueError,KeyError,TypeError,AttributeError) as exc:
                response.failure(f"Read validation: {exc}")

    @task(4)
    def large_measurements(self):self.read("large_geojson","measurements/")

    @task(3)
    def medium_measurements(self):self.read("medium_shapefile","measurements/")

    @task(2)
    def complex_measurements(self):self.read("complex_geojson","measurements/")

    @task(1)
    def large_summary(self):self.read("large_geojson","summary/")

    @task(1)
    def large_quality(self):self.read("large_geojson","quality/")

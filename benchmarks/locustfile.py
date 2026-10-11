"""Local-only baseline workload for the submitted GeoInsight FastAPI contract.

Each Locust user uploads ONE known-good synthetic KML during setup, then
repeatedly reads that stored record. Setup requests have their own metric
name, so exclude SETUP when comparing GET throughput and latency.

Safety: refuse any target other than http://127.0.0.1:18130.
No changes to server source or production data are required.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from locust import HttpUser, between, task
from locust.exception import StopUser

# Based on the known-good fixture already exercised in aereo_tests/test_engine.py.
SYNTHETIC_KML = b'''<?xml version="1.0" encoding="UTF-8"?>
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


def _assert_local_target(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (parsed.scheme, parsed.hostname, parsed.port) != ("http", "127.0.0.1", 18130):
        raise RuntimeError(
            "Benchmark blocked: --host MUST be http://127.0.0.1:18130; "
            "never benchmark the submitted Render app."
        )


class GeoInsightReadUser(HttpUser):
    """Small, controlled GET workload; no repeated uploads during tasks."""

    # CLI --host is still required; the explicit guard prevents remote runs.
    host = "http://127.0.0.1:18130"
    wait_time = between(0.8, 1.8)

    def on_start(self) -> None:
        _assert_local_target(str(self.client.base_url))
        self.file_id = ""
        with self.client.post(
            "/api/files/",
            name="SETUP POST /api/files/ (exclude from GET stats)",
            files={"file": (
                "geoinsight-benchmark.kml", SYNTHETIC_KML,
                "application/vnd.google-earth.kml+xml",
            )},
            catch_response=True,
            timeout=25,
        ) as response:
            if response.status_code != 201:
                response.failure(f"Setup upload returned HTTP {response.status_code}: {response.text[:160]}")
                raise StopUser()
            try:
                payload = response.json()
                file_id = payload["id"]
                if (len(file_id) != 32 or payload["feature_count"] != 3
                        or payload["successful_measurements"] != 2
                        or payload["status"] != "COMPLETED"):
                    raise ValueError(f"Unexpected setup payload: {payload!r}")
            except (ValueError, KeyError, TypeError) as exc:
                response.failure(f"Setup verification failed: {exc}")
                raise StopUser() from exc
            response.success()
            self.file_id = file_id

    @task(3)
    def metadata(self) -> None:
        with self.client.get(
            f"/api/files/{self.file_id}/",
            name="GET /api/files/{id}/",
            catch_response=True,
            timeout=15,
        ) as response:
            try:
                data = response.json()
                if (response.status_code != 200 or data.get("id") != self.file_id
                        or data.get("feature_count") != 3
                        or data.get("status") != "COMPLETED"):
                    raise ValueError("Metadata response does not match seeded file")
            except (ValueError, TypeError) as exc:
                response.failure(str(exc))

    @task(3)
    def measurements(self) -> None:
        with self.client.get(
            f"/api/files/{self.file_id}/measurements/",
            name="GET /api/files/{id}/measurements/",
            catch_response=True,
            timeout=15,
        ) as response:
            try:
                data = response.json()
                features = data.get("measurements", [])
                kinds = {f.get("geometry_type"): f for f in features}
                polygon = kinds.get("Polygon", {})
                line = kinds.get("LineString", {})
                point = kinds.get("Point", {})
                if not (
                    response.status_code == 200
                    and data.get("file_id") == self.file_id
                    and len(features) == 3
                    and polygon.get("measurement", {}).get("value", 0) > 1_000_000
                    and line.get("measurement", {}).get("value", 0) > 0
                    and point.get("status") == "NOT_APPLICABLE"
                    and point.get("measurement") is None
                ):
                    raise ValueError("Incorrect measurements or per-feature status")
            except (ValueError, TypeError, AttributeError) as exc:
                response.failure(str(exc))

    @task(1)
    def quality(self) -> None:
        with self.client.get(
            f"/api/files/{self.file_id}/quality/",
            name="GET /api/files/{id}/quality/",
            catch_response=True,
            timeout=15,
        ) as response:
            try:
                data = response.json()
                if (response.status_code != 200 or data.get("file_id") != self.file_id
                        or data["summary"]["total_features"] != 3):
                    raise ValueError("Unexpected quality result")
            except (ValueError, KeyError, TypeError) as exc:
                response.failure(str(exc))

    @task(1)
    def summary(self) -> None:
        with self.client.get(
            f"/api/files/{self.file_id}/summary/",
            name="GET /api/files/{id}/summary/",
            catch_response=True,
            timeout=15,
        ) as response:
            try:
                data = response.json()
                if (response.status_code != 200 or data.get("file_id") != self.file_id
                        or data.get("counts", {}).get("measured") != 2):
                    raise ValueError("Unexpected measurement summary")
            except (ValueError, TypeError) as exc:
                response.failure(str(exc))

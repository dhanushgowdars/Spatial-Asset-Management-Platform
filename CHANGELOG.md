# Changelog — GeoInsight

All notable GeoInsight assessment enhancements are recorded here. The original Spatial Asset Management Platform is a separate legacy codebase in this repository; this changelog describes the **GeoInsight** application.

## [v2.0.0] — GeoInsight V2 public release (2026-10-12)

> **Deployment status:** V2 was merged through [pull request #1](https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform/pull/1), deployed on Render from commit `23e7c3a`, and verified with a public upload, known-size measurement, comparison and PDF download. For the local benchmark and test scope see [V2 verification](docs/GEOINSIGHT_V2_VERIFICATION.md).

### Phase 1 — Reproducible workloads
- Added synthetic GIS benchmark fixtures and a Locust-based harness for uploads and seeded reads: mixed GeoJSON, larger feature sets, complex geometries, Shapefile, KML, and KMZ.
- Established local baseline read timings. Exact reported Locust aggregate rows from locally retained CSVs are recorded in the verification document (62 seeded-read requests before cache and 72 after cache; mean **143.53 → 14.67 ms**, P95 **300 → 60 ms**). These different, small local runs are not certified production performance.

### Phase 2 — Upload reliability
- Moved blocking upload database persistence off the FastAPI async event loop and maintained DB-session ownership for threaded work.
- Added bounded upload admission, responding with HTTP 503 and `Retry-After` under deliberate overload.

### Phase 3 — Request protection
- Added in-memory, per-peer upload rate limiting (default 120/minute), with HTTP 429 and `Retry-After`.
- Added bounded concurrent spatial-analysis admission (default 4), returning HTTP 503 on overload.

### Phase 4 — Faster conditional reads
- Added bounded, process-local TTL/LRU response caching for measurements and GeoJSON (default 32 entries, 32 MiB total, 4 MiB/item, 60 seconds).
- Added ETags, conditional `If-None-Match` handling with HTTP 304, and cache-state headers.

### Phase 5 — Observability and regression coverage
- Added per-request IDs, `Server-Timing`, structured HTTP request logs, and better handling of middleware-generated rejection responses.
- Expanded isolated regression tests for overload, rate-limiting, telemetry, cache, and error-path behavior.

### Phase 6 — Survey evidence and decision support
- Added persisted-results verification JSON, source SHA-256 fingerprint, CRS/method/limitations and feature evidence.
- Added React **Survey Evidence Passport** and **Survey Change Decision Brief** with deterministic comparison evidence and export.
- Verified known-size survey comparison: each footprint 10,000 m², with 5,000 m² added, removed and unchanged, respectively (0 m² net; IoU 33.33%).

### Phase 7 — Reviewer experience and reporting
- Added client-side feature-table pagination (50 records/page) and synchronized, animated feature-to-map focus.
- Added bounded ReportLab survey PDF download with feature appendix and stored provenance, then polished m² notation and polygon perimeter.
- Revalidated in a production Linux Docker image against SQLite, and separately against PostgreSQL 16 with successful stored-data retrieval after an application restart (see release gate below).

### Reported verification
- **160/160** isolated Aereo backend regression tests and **4/4** supplementary PDF presentation tests passed on Windows/Python 3.11.8.
- Frontend ESLint and production Vite build passed. The main bundled JS chunk reported a nonblocking size warning.
- First production Docker image started, served five HTTP routes with 200 responses, processed a real sample and generated PDF downloads.
- PostgreSQL-backed upload, stored measurement, verification JSON/PDF and retrieval after app restart passed.
- **Final post-polish image was rebuilt and smoke-tested** locally: health, Shapefile upload and PDF export succeeded; downloaded PDF was **4,912 bytes** and displayed `m²`. Subsequently V2 passed the two GitHub PR CI checks and deployed live on Render from `23e7c3a`; public survey analysis, a 6/6 sample comparison, and a two-page report with a 400 m perimeter were verified.

### Limits
- In-memory protections and cache are **per application process**, not distributed. No authentication, private upload tenancy, user deletion/retention or certified survey accuracy is claimed.
- Benchmarks are limited, synthetic local observations, mostly against SQLite—not production SLOs, production load tests, or security audits.

## Original submitted GeoInsight (pre-V2)
- Implemented KML and zipped-Shapefile ingestion with optional GeoJSON/KMZ, projected CRS-aware measurement, per-feature validation/evidence, persisted results and REST endpoints.
- Added the React/Leaflet measurement and quality workspaces, deterministic survey comparison, topology, route/zone analysis, and downloadable CSV/GeoJSON.
- Documented original implementation and public assessment deployment in [README.md](README.md) and [technical guide](docs/GEOINSIGHT_TECHNICAL_GUIDE.md).

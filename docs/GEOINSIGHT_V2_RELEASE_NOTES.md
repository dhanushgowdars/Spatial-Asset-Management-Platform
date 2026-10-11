# GeoInsight V2 — Release Notes

**Status:** V2 is **live on Render**, built from GitHub merge commit `23e7c3a` after both PR CI checks passed. Release tag: `v2.0.0`. Core public upload, measurement, sample comparison and PDF export were smoke-tested.

## What V2 adds

GeoInsight remains a single FastAPI/React/Leaflet application. V2 reinforces the assignment's GIS measurement and spatial analysis API with practical backend reliability, observability, reproducible synthetic testing and reviewer-focused evidence export.

**Engineering highlights**

- **Reliability and overload policy:** nonblocking upload persistence, bounded upload and analysis admission, HTTP 503 + `Retry-After` under overload, and HTTP 429 for per-peer upload rate limiting.
- **Conditional read optimization:** bounded per-process LRU/TTL caching, ETags, HTTP 304 responses and cache-hit metadata.
- **Observability:** `X-Request-ID`, `Server-Timing` and structured HTTP request logging, including rejection paths.
- **Evidence and trust:** source-upload SHA-256, stored-result verification JSON and printable PDF with CRS, method, warnings and bounded feature appendix.
- **Spatial decision support:** a React survey-change brief showing that equal net area does not imply identical boundaries, with map-based explanation and JSON export.
- **Usability:** large feature-list pagination and synchronized table↔map focus; clear missing/invalid geometry handling and projected units.
- **Production validation:** a Linux Docker build, API/frontend smoke tests, Postgres 16 compatibility and successful stored result retrieval across an application restart.

## Verification evidence

| Check | Recorded local result | Scope |
| --- | --- | --- |
| Backend tests | 160 passed | Isolated `aereo_tests`, Windows/Python 3.11.8 |
| PDF display tests | 4 passed | Supplementary checks, after the PDF unit/perimeter polish |
| Frontend | 44 Node tests passed; ESLint and Vite build passed | Local tests and expanded GitHub CI workflow |
| Docker | Final post-polish image rebuilt, health/upload/PDF passed; local report **4,912 bytes** | Local Linux Docker image; Render runs the verified V2 merge commit |
| PostgreSQL 16 | Upload, retrieval, report/PDF and app-restart persistence passed | Local isolated Docker network and disposable DB |
| Synthetic geometry | 100 m square = 10,000 m², perimeter 400 m | EPSG:32643; no real land-survey certification |
| Change detection | 5,000 m² added, 5,000 m² removed, 5,000 m² shared | Two synthetic 10,000 m² footprints; IoU 33.33% |

See [complete seven-phase verification](GEOINSIGHT_V2_VERIFICATION.md) for workload descriptions, approximate latency observations, confidence limits, and the original-submission vs V2 distinction. See [V2 architecture](GEOINSIGHT_V2_ARCHITECTURE.md) for request/data flow details.

## Reviewer quick start (live V2)

1. Open the GeoInsight `/geospatial` workspace or `/docs` on the verified deployment URL.
2. Upload a synthetic `.geojson`, `.kml`, `.kmz` or zipped ESRI Shapefile and inspect metric CRS, feature table and map.
3. Download CSV/GeoJSON, verification JSON and PDF.
4. Compare the two known-size synthetic polygons in `/geospatial/compare` to review the derived change brief and map.

**Important:** this public assessment UI does not enforce accounts or user-scoped access. Only upload public/synthetic datasets. Caches and rate limits are process-local; measurements are planar projections, not cadastral certification.

## Publishing checklist

- [x] Rebuild final Docker image from polished source and check upload + PDF locally.
- [x] Stage and audit the 60-file V2 commit; exclude temporary and generated data.
- [x] Merge V2 PR #1 after both GitHub CI checks passed.
- [x] Confirm Render branch, build path, auto-deploy status and deployed commit.
- [x] Verify public health, upload, known-size measurement, comparison and PDF download.
- [ ] Publish GitHub `v2.0.0` release after merging this documentation update.

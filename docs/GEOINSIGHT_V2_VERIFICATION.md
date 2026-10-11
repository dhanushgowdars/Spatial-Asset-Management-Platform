# GeoInsight V2 — Engineering Hardening and Local Verification Record

> **Status:** V2 was deployed to the public Render service on 2026-10-12 from GitHub merge commit `23e7c3a`, after the local release checks and GitHub PR CI passed. The workloads and latency figures in this document remain **local synthetic observations**, not audited production performance objectives.

## Scope, evidence and trust boundaries

- Worktree: `GeoInsight-Hardening-Lab`, branch `feature/geoinsight-hardening-local`, based on original submitted `b33c5b4`. The original checkout and FaultWeave were not changed by the V2 test packages.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Shapely, pyproj. Frontend: React + Leaflet. The GIS calculations use projected geometry in Python, **not PostGIS queries**.
- Most controlled performance runs used **local SQLite**, a single locally run API process, synthetic known-size fixtures and small user counts. A separate later functionality smoke test used **PostgreSQL 16 in Docker**.
- Measurement accuracy claims are constrained to projected 2D geometry and synthetic fixture expectations; they do not establish field-survey precision, official property boundaries, customer-dataset suitability or security certification.
- The original baseline test suite and historical public CI statuses are documented in the original README and should not be conflated with the expanded local V2 suite.

## Phase 1 — Deterministic benchmark fixtures and initial measurements

Synthetic workloads were generated locally with independent projected-coordinate oracles and parsed by the real GIS engine. They were designed to expose realistic parsing, JSON persistence and read cost rather than just trivial one-feature payloads.

| Fixture / workload | Geometry mix or purpose | Interpretation |
| --- | --- | --- |
| `medium_250.geojson` | **200 polygons** of 100 m × 100 m + **50 lines** of 120 m; WGS84 source | Expected **2,000,000 m²** summed area and **6,000 m** line length; not geometric polygon union. |
| `large_1200.geojson` | **960 polygons**, **240 lines** | Large feature-count ingestion/read workload; not proof of maximum supported capacity. |
| `complex_80.geojson` | 20 polygons with holes, 20 multipart polygons, 40 dense curves | Harder geometry and JSON persistence workload; uses separate geometry oracles. |
| `medium_250.zip` | 250 projected Shapefile polygons with `.shp/.shx/.dbf/.prj` | Format compatibility plus known-size geometry oracle. |
| `medium_150.kml` | 100 polygons, 25 lines, 25 points | Correctly distinguishes measurable geometries and Points (not applicable). |
| `medium_150.kmz` | Zipped KML with the same 150 geometries | KMZ archive/format compatibility. |

The fixture generator checks metric oracles against projected-source values, using 0.02% tolerance with a minimum of 0.25 m or m². Controlled Locust profiles separated uploads (`POST`), verification reads and seeded-read GETs; aggregate RPS was **not** treated as upload throughput.

**Earlier endpoint-specific baseline observations (approximate):** large measurement retrieval p95 ~380 ms, complex retrieval p95 ~310 ms, zipped Shapefile retrieval p95 ~170 ms. These are **different endpoint samples** from the aggregated run results below; do not interchange them with the whole-profile P95 figures. Hardware counters and full run-environment metadata have not been independently verified.

### Exact recorded Locust aggregates (local synthetic workloads)

The following values are transcribed from the Locust `Aggregated` rows of the named CSVs in the isolated worktree. Each run uses its own workload, user count, duration and sample; **these are not a same-conditions cross-workload comparison**.

| Dataset / profile | Requests | Failed | Mean (ms) | Median (ms) | P95 (ms) | Requests/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Medium, 2 users (`medium_2users_stats.csv`) | 58 | 0 | 504.03 | 290 | 1,500 | 1.993 |
| Large, 1 user (`large_1user_stats.csv`) | 14 | 0 | 1,034.82 | 1,300 | 2,500 | 0.494 |
| Complex, 1 user (`complex_1user_stats.csv`) | 24 | 0 | 301.89 | 310 | 550 | 0.865 |
| Seeded reads before cache, 2 users (`seeded_reads_2users_stats.csv`) | 62 | 0 | 143.53 | 150 | 300 | 2.135 |
| Seeded reads after Phase 4A cache, 2 users (`seeded_reads_phase4a_2users_stats.csv`) | 72 | 0 | 14.67 | 5 | 60 | 2.552 |

**Observed read comparison:** mean latency **143.53 → 14.67 ms** (~**9.8×** lower), median **150 → 5 ms** (**30×** lower) and P95 **300 → 60 ms** (**5×** lower). The two read runs had different request counts (**62 vs 72**) and measured throughput (~2.135 vs ~2.552 requests/s). This is evidence of faster **local cached reads**, not a production guarantee, controlled multi-run study, general upload-throughput improvement or horizontal scalability. Locust's aggregate request count and Requests/s include whichever HTTP requests the profile made; do not mislabel them as file-upload throughput. The underlying CSVs remain local under `benchmarks/v2/output/` and are excluded from Git by default.


## Phase 2 — Upload reliability and concurrency protection

- **2A:** moved the synchronous database commit/refresh work off the FastAPI async upload event loop, preserving isolated DB session ownership around threaded operations. The objective was nonblocking behavior, **not** an unsubstantiated speed claim.
- **2B:** bounded simultaneous upload work using an admission semaphore; default reported capacity 4. Excess work returns **503 Service Unavailable** with `Retry-After` instead of unlimited queueing.
- Controlled overload demonstration with capacity **1** and six simultaneous clients: **1 HTTP 201**, **5 HTTP 503**; `/health` remained available and the service recovered. This is intentionally the expected overload policy, not six successful uploads.

## Phase 3 — Limiting abusive or excessive work

- **3A:** in-memory per-peer rate limiting on `POST /api/files/`, default **120 requests per minute**, responding **429 Too Many Requests** with `Retry-After` on excess submissions.
- **3B:** bounded concurrent geospatial analyses (default **4**); overload uses **503** with retry semantics.
- Scope: these are **process-local**, best-effort controls. Multiple workers/replicas do not share counts or the concurrency limiter; per-IP rate limiting is not a substitute for authenticated user quotas. Rejecting requests under deliberate overload is correct, not failed functional processing.

## Phase 4 — Bounded cache and conditional reads

- Local in-memory TTL/LRU read cache for measurement and map GeoJSON GET endpoints. Reported defaults: **32 entries**, **32 MiB aggregate**, **4 MiB per item**, **60-second TTL**.
- Supports ETag + `If-None-Match` → **304 Not Modified** and preserves ordinary 404 behavior; sends `X-GeoInsight-Cache` headers for inspection. This does **not** make uploaded results globally cached or durable.
- **Illustrative user-reported local samples:** large measurements GET p95 ~380 ms in a baseline sample compared with ~17 ms in a warm-cache sample; p50 roughly ~200 ms vs ~5 ms. These are short, context-dependent samples rather than a controlled same-conditions longitudinal benchmark. **No 20×/40× production speedup claim is justified**.
- In the recorded seeded-read Locust aggregates, **62 requests before caching** and **72 after caching** both had **zero recorded failures**. The after-cache P95 was **60 ms** versus **300 ms** before. An earlier **73-request** zero-error trial was a **separate** observation; these counts should not be conflated. This is low-load local SQLite evidence, not a high-concurrency throughput claim.

## Phase 5 — Request tracing, timing, rejection-path reliability

- **5A:** unique `X-Request-ID`, `Server-Timing`, structured request logs with route/status/duration, including verified 200 and 404 paths.
- **5B:** regression-fixture environment isolation and 7 dedicated reliability checks. Middleware ordering adjusted so rate-limited 429 responses also carry request metadata/timing; live probes covered 415 and 429 rejections.
- Logging does not provide distributed tracing or automatic production monitoring. Some middleware-rejected requests may have an unmatched route label.

## Phase 6 — Provenance, printable evidence and survey decisions

- **6A:** `GET /api/files/{file_id}/verification-report/` returns a stored-results JSON report with source-upload SHA-256, source/measurement CRS, processing counts, per-feature results, warnings and clear limitations. It is **not** independent recalculation/certification.
- **6B:** React **Survey Evidence Passport** shows statuses, warnings, CRS, original upload fingerprint and exports; verified in a browser against a 100 m square and a 250-feature dataset.
- **6C:** **Survey Change Decision Brief** and JSON export from the deterministic polygon comparison; equal net area is explicitly distinguished from unchanged geometry. Synthetic baseline/current, each 10,000 m², produce **5,000 m² added**, **5,000 m² removed**, **5,000 m² overlap**, **0 m² net**, and **33.33% intersection/union**. The map and feature inspector expose derived geometries and projected methods.

## Phase 7 — Usability, PDF and container/database validation

- **7A:** feature table paginated **50 records per page** in the browser (not backend pagination). Map selection navigates to the proper table page; clicking a table record focuses the geometry and smoothly scrolls to the map. The negative-zero display artifact was fixed.
- **7B:** bounded PDF survey report generated from persisted JSON through ReportLab. Download endpoint `GET /api/files/{file_id}/verification-report.pdf`, with proper PDF media type and attachment headers, 404 handling, SHA-256/CRS/status/method/limitations and feature appendix. Eight new PDF regression tests were added; a malformed report count mismatch was fixed by validating before reading summary internals.
- **7C:** PDF presentation changed to show **m²** notation and polygon perimeter; **4/4** PDF presentation tests passed. Local production Docker image built and successfully served the app; Linux container returned HTTP **200** for `/health`, `/geospatial`, `/geospatial/compare`, `/geospatial/quality`, `/openapi.json`. A zipped Shapefile uploaded and a PDF downloaded. A separate isolated PostgreSQL 16 setup successfully stored/retrieved a 10,000 m² measurement and generated a PDF. **After restarting only the application container**, the same PostgreSQL-backed file still returned **10,000.0 m²**.
- **Final local container smoke verification completed after PDF polish:** the final Docker image was rebuilt successfully, returned `healthy`, uploaded `plot-utm43n.zip`, returned the stored area **10,000 m²**, and produced a **4,912-byte** PDF with the updated `m²` notation (first page visually checked). The **400 m perimeter** was confirmed visually on page 2 of the public PDF. The final Docker/image test remains **local** evidence; separately, the live Render V2 deployment passed measurement, comparison and PDF smoke tests.

## Test matrix and recorded results

| Test/evidence | Result reported by user | Qualification |
| --- | --- | --- |
| V2 backend regression suite, isolated `aereo_tests` | **160 passed** (12.85s in final reported run) | Windows Python 3.11.8; includes 8 PDF tests. No general root pytest. |
| PDF presentation-specific tests | **4 passed** (0.72s) | Additional locally supplied validation checks; not part of the 160 collection. |
| Frontend ESLint | **Passed** | V2 local worktree. |
| Frontend Vite production build | **Passed** | Nonblocking warning: JS chunk over 500 kB; GitHub PR React CI check also passed. |
| Selected React/component regression files | **44/44 passed** in one Node run | Seven frontend Node test modules; pagination, decision brief, evidence panel, negative-zero and older contracts. |
| Git `diff --check` | **No whitespace errors** | CRLF/LF conversion notice on `.dockerignore` is non-fatal. |
| SQLite-backed production container | **Started**, 5 tested HTTP routes **200** | Real zipped Shapefile upload, downloaded PDF roughly **4.9 kB**. |
| PostgreSQL-backed production container | **Healthy**, 1 feature stored and read | Verification report schema 1.0; PDF roughly **4.9 kB**. |
| PostgreSQL persistence across app restart | **Passed**, stored file still returns **10,000 m²** | Database container was kept running; **not** backup/restore or total database-container deletion test. |
| Baseline/seeded Locust reads | Raw local aggregate records: **62 baseline read requests, 0 failures**; **72 after-cache read requests, 0 failures**; P95 **300 → 60 ms** | Different short synthetic SQLite runs; original 73-request observation was separate. See exact Locust table above. |

## Limits and release checklist

1. **No authentication or per-user data isolation** is claimed. The local rate limiter and admission controls provide availability protections, not access control. Reviewers should upload public/synthetic data only.
2. **No survey certification** or independent GIS recomputation of stored reports is claimed. CRS projection distortion, invalid geometry and arithmetic area sums require interpretation.
3. **No production load-test, security audit or production latency SLO** was established from the local benchmarks. Raw CSVs were inspected by the user and aggregate values are recorded above; the CSVs remain in the isolated local `benchmarks/v2/output/` folder and are ignored by Git unless a separately reviewed evidence export is prepared.
4. **V2 is now live** on Render from `23e7c3a`; public upload, measurement evidence, comparison and PDF were verified. Live-service database restart persistence, security testing and production load testing were not performed.
5. **Release gates completed:** staged-source audit, verified Git author, 60-file V2 commit, both PR CI checks, merge into `main`, Render deployment, public upload/measurement/comparison and PDF checks. **Remaining:** publish GitHub tag and release notes after documentation reconciliation.

### Safe local verification commands

From the isolated GeoInsight V2 worktree:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest aereo_tests -q
Push-Location frontend
npm run lint
npm run build
Pop-Location
git diff --check
```

Do **not** run the older root-level `pytest` or indiscriminate `git add .`. Do not stop unrelated Docker containers/services. Production must use the current reviewed release build, not an old pre-polish image.

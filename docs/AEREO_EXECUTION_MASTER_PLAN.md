# GeoInsight — Aereo Internship Master Execution Plan

**Version:** 1.0 (scope freeze)
**Established:** Friday, 9 October 2026, approximately 23:00 IST
**Official date communicated by hiring manager:** Sunday, 11 October 2026, **EOD** (exact hour not stated).
**Internal goal:** submit by **Sunday, 11 October, 13:00 IST**; personal hard-stop **18:00 IST**. Never rely on EOD meaning 23:59.
**Repository:** `dhanushgowdars/Spatial-Asset-Management-Platform`
**Current work branch:** `feature/aereo-geospatial-measurements`
**Track status in:** `docs/AEREO_PHASE_TRACKER.md`. Update at every verified checkpoint.
**Assignment source:** `Geospatial File Measurement API(1).docx` supplied in the application form.

## 0. Mission and selection strategy

Build a **reliable, easily testable survey-file validation and measurement service** with an interactive reviewer interface. Its distinguishing qualities are **correct geometry processing, explainable CRS/measurements, input-quality diagnostics, interoperable output, independent tests, and a reproducible public deployment**. Do not equate extra features with being selected: Aereo decides selection, and no feature guarantees an interview.

Aereo's separate 2026 GIS Developer listing describes large-scale geospatial-file handling, Python, spatial analysis, validation, web maps, and reliability. This is background evidence of domain relevance, **not** a change to the internship assignment: https://hire.aereonauts.aereo.io/. Aereo's own site describes mapping, survey analytics and infrastructure applications: https://aereo.io/.

**Product pitch:** *From geospatial file to trustworthy, auditable measurement, with visible geometry, QA findings, units, and shareable machine-readable results.*

## 1. Non-negotiable assessment contract

Implement and keep backward-compatible:

- Accept `.kml` and `.zip` containing one Shapefile. Validate archive components and filename safety.
- Extract **feature ID/index, geometry type, geometry, source CRS, and properties/attributes** for each feature.
- **Polygon:** metric area. **LineString:** metric length. **Point:** no measurement required, but its geometry/metadata must be present when valid.
- Never calculate area or distance directly in longitude/latitude degrees. Convert from geographic coordinates to a suitable **projected CRS**; record the chosen CRS and limitations.
- Handle unsupported or malformed features without crashing, preserving valid results where feasible.
- Keep `POST /api/files/`, `GET /api/files/{id}/`, `GET /api/files/{id}/measurements/` with documented request/response contracts.
- README: setup, run, API calls, examples, architecture, processing and measurement flow, CRS handling, design decisions, **learning and future scope**, and public GitHub repository.
- A live deployment and interactive frontend are differentiators but **not stated as mandatory by the supplied assignment**. Do not risk the required API to finish optional UI.

## 2. Verified baseline and honest status

Evidence available **as of 9 October, before this plan's application**:

- User verified `18 passed, 1 warning` via `python -m pytest aereo_tests -q` on Windows Python 3.11.8. The warning is Starlette/httpx deprecation, not a failed test.
- `aereo.api:app` runs locally on `127.0.0.1:18130`; `/docs` and `/openapi.json` returned HTTP 200.
- Frontend Vite lint and production build passed after patch; 148 modules compiled. App at `/geospatial` and browser screenshots show working sample upload, map, rows, details and a corrected key-free geometry-only map view.
- Independent **synthetic** file QA: KML hole polygon 7,500 m², 500 m line, Point N/A; Shapefile parcels 10,000 + 2,500 m²; Shapefile lines 500 + 5 m. Missing CRS remains unmeasured; malformed KML, missing `.dbf`, and ZIP traversal are rejected. These are **not external real-world field survey files**.
- Current Aereo code introduced via prior packages runs as a **standalone API** (`aereo/api.py`) with an isolated SQLite database by default. It does **not** yet prove managed PostgreSQL persistence or public deployment.
- **Not verified yet:** independent external GIS fixtures, sustained/large-file behavior, cloud deployment, public browser smoke tests, CI, npm vulnerability remediation, final README or actual submission.
- Docker Desktop Linux engine and original `geoasset_db` PostGIS 3.4 were observed healthy. Do **not** reset or remove their Docker volumes. Original code's legacy Pytest fixtures can drop tables in the **test database**: do not run legacy tests until isolated test DB is confirmed.

## 3. Existing work: reuse, do not duplicate

### 3.1 Original repository `main` (inspected on GitHub)

Original services/routes already have:

| Capability | Verified source/function | Reuse decision |
| --- | --- | --- |
| Nearby/nearest assets and distance | `app/services/asset_service.py`, `app/repositories/asset_repository.py` | Keep as separate asset product; no new Aereo route for this |
| Bounding-box lookup | `get_assets_in_bounding_box` | Reuse reasoning only if feature query is needed |
| Geofencing | `get_assets_in_geofence` | Not Aereo release priority |
| Buffer around point/asset | `generate_buffer` | **Defer** for Aereo; more work than reviewer value |
| Polygon area | `calculate_polygon_area`, PostGIS `ST_Area(geography)` | Already proven concept; Aereo implementation uses per-file CRS engine |
| Centroid | `calculate_polygon_centroid` | **Add to report for uploaded polygons**, without duplicating asset code |
| Line/route length | `calculate_route_length`, PostGIS `ST_Length(geography)` | Already proven concept; Aereo engine already measures lines |
| Route intersection with polygon | `check_route_intersection` | **Defer** unless all release gates pass |
| Asset CRUD, soft delete, JWT/RBAC, audit, analytics | Existing routes/models | Preserve intact; keep reviewer assessment flow separate |

### 3.2 New standalone Aereo engine (inspected from Milestone 1 package)

`app/services/geospatial/engine.py` **already includes**:

- KML `Point`, `LineString`, `Polygon` (including holes), and `MultiGeometry` → `MultiPoint`, `MultiLineString`, `MultiPolygon` or `GeometryCollection`.
- Zipped Shapefile parsing, `.prj` CRS detection, `.cpg` encoding support, attribute extraction, and one-Shapefile-per-archive policy.
- `Shapely` geometry validity checks, per-feature errors, no fake measurement when CRS missing, and missing geometry handling.
- WGS84 display geometry plus local UTM / nonlocal LAEA-or-AEQD projected measurement logic, `always_xy=True`, and distortion warnings for large/polar geometries.
- Metric areas for Polygon/MultiPolygon, lengths for LineString/MultiLineString, and `NOT_APPLICABLE` for Point/MultiPoint.
- Defensive limits: 10 MiB upload, 50 MiB expanded ZIP, max 5,000 features, max 250,000 vertices per geometry, max 40 ZIP entries; ZIP traversal and XML entity protections.
- `aereo/api.py`: 3 required endpoints, a GeoJSON map endpoint, database-persisted results, and `/health`.

**Important conclusion:** Do not reimplement MultiPolygon, MultiLineString, or basic geometry validity; extend existing tested code. `GeometryCollection` is not currently a measured geometry type and must be identified as unsupported or handled explicitly after tests.

## 4. Architecture and design constraints

```text
Existing GitHub repository / feature branch
├─ Original authenticated asset-management code     [preserve]
├─ aereo/api.py                                       [standalone assessment API]
│    ├─ required file-upload + file-info + measurement endpoints
│    ├─ optional summary, quality, history, export endpoints
│    └─ isolated database models/results store
├─ app/services/geospatial/engine.py                 [pure processing/measurement]
│    ├─ validated parsers: KML, Shapefile ZIP, then GeoJSON/KMZ
│    ├─ canonical geometry, properties, source CRS
│    ├─ validation + feature-level findings
│    └─ projection + metric measurement + provenance
├─ aereo_tests/                                       [isolated Pytest fixtures]
└─ frontend/src/pages/Geospatial/                    [real backend data only]
     ├─ Import / Try sample -> Explore map -> Verify report
     └─ Quality summary -> Feature details -> Export
```

- **One source of truth:** measurement engine returns data; React only formats numbers and displays GeoJSON. Never calculate authoritative area/length in JavaScript.
- Every result must bind original filename/hash, feature ID, geometry type, source CRS, measurement CRS, units, computation method, status, and warnings/errors.
- Keep original geometry/attributes available in the result, and return properly transformed WGS84 display geometry for Leaflet.
- No mandatory account registration for reviewers; ensure safe public upload controls and avoid exposing private asset APIs.
- Aereo DB namespace/table must not alter existing asset data. Use isolated SQLite locally; persistent PostgreSQL for hosted deployment if viable. Never depend on ephemeral local SQLite in production.
- Prefer simple bounded synchronous processing first. Document processing limits, no claim of PB-scale support or production-grade queue throughput.
- Avoid unrelated AI, 3D, DEM/GeoTIFF elevation, stockpile volumes, and speculative precision/accuracy percentages.

## 5. Locked priorities — high-impact additions

### P0 / must finish for submission (no negotiation)

1. Three mandatory endpoints + existing `.kml` and zipped Shapefile ingestion remain stable; `aereo_tests` and local browser reference workflows pass.
2. Independent **external, legitimately sourced** KML/Shapefile GIS datasets (not generated by the project) for compatibility tests, including one modest local-area dataset and one large/complex vector dataset used only for parsing, where appropriate.
3. CRS unit/axis test matrix: WGS84, projected metre, projected foot if fixture available, holes, multipart, invalid and missing CRS; documented tolerance, no invented measurements.
4. CI running isolated backend tests and frontend lint/build; secure ZIP/XML validation, meaningful error responses.
5. Reproducible Docker build, persistent database-backed public deployment *if it can be stabilized*, actual public HTTP upload→GET→GeoJSON/download→refresh/restart smoke test.
6. Dedicated, concise assignment-first README, honest limitations and examples; submit public main repo **before internal cutoff**.

### P1 / high-value differentiators (add after P0 baseline is pushed)

**P1-A — Survey QA report (best differentiation)**
- Reuse current `is_valid` checks; add structured, typed diagnostic codes: `INVALID_GEOMETRY`, `EMPTY_GEOMETRY`, `CRS_MISSING`, `UNSUPPORTED_GEOMETRY`, `TRANSFORM_FAILED`, `PROJECTION_DISTORTION_WARNING`, `PARSE_FAILED`.
- Separate **feature statuses** `MEASURED`, `NOT_APPLICABLE`, `FAILED`, `UNSUPPORTED` from **file statuses** `COMPLETED`, `COMPLETED_WITH_ERRORS` (do not mislabel `NOT_APPLICABLE` as failure).
- `GET /api/files/{id}/quality/` returns counts, issue IDs, severity and explanations; show a QA panel beside results. No auto-repair of polygons without explicit safeguards. No fake "quality score".
- Tests: mixed valid/invalid features; missing `.prj`; malformed XML/ZIP; per-feature report matches summary.

**P1-B — Interoperability: GeoJSON and KMZ**
- Add `.geojson` (RFC 7946 WGS84 longitude, latitude); preserve properties/feature IDs; reject non-GeoJSON JSON and invalid coordinate ranges; test collection and multipart cases. Do not silently assume arbitrary projected coordinates are WGS84.
- Add `.kmz` by secure ZIP inspection and selecting its KML entry; protect traversal, archive-bomb limits, DTD/entities, duplicate paths; explicitly reject unsupported packages.
- These formats are **extras** and must never break required Shapefile ZIP or KML support.

**P1-C — Measurement evidence and useful secondary metrics**
- Polygon/MultiPolygon: existing area + **perimeter**; centroid and WGS84 bounding box (clear units and projection where appropriate).
- LineString/MultiLineString: existing total length + segment/parts count, start/end positions if meaningful.
- Point/MultiPoint: lat/lon / coordinate details and properties; **not** fabricated area or length.
- Add `measurement_method`, source/projection provenance and warnings. Keep existing `measurement` fields stable; add new optional schema fields.
- API JSON retains high precision; frontend rounds and labels m, km, m², km² explicitly.

**P1-D — Quality and export endpoints, not endpoint sprawl**
- `GET /api/files/` (paginated recent uploads, bounded disclosure; public privacy/rate-limit policy required).
- `GET /api/files/{id}/summary/` (counts and aggregate area/length; do not sum inappropriate mixed geographic extents without warning).
- `GET /api/files/{id}/quality/` (structured validation findings).
- `GET /api/files/{id}/export/?format=csv|geojson` (downloadable measurements and standardized geometries; existing `/geojson/` remains).
- Tests cover pagination, response shape, CSV header/escaping, encoded attribute values, exports equal results.

**P1-E — Reviewer UX upgrades only after backend checks**
- Show file status and summary **before** map; support Import → Explore → Verify with obvious step navigation.
- Geometry-only key-free option always works; Streets map is optional best-effort. Current tile view uses OpenStreetMap; no new paid tile dependency.
- Full table row selects + scrolls/focuses feature; fit-all and fit-selected; visible hole / multipart; accessibility and clear small-feature styling.
- Quality panel with failed/warning feature badges, CRS provenance, per-feature details, and downloadable report; link Swagger and README.
- Sample buttons use same actual API as user uploads, never precomputed demo responses.

### P2 / stretch only after hosted P0/P1 all verified

- **2D footprint comparison** between two compatible polygon datasets: overlap/added/removed area, geometries rendered on common projected CRS. Only if testable and explainable. **Do not call it 3D change detection or volumetrics.**
- GeoPackage (`.gpkg`) is OGC standard but format/parsing/multiple-layer complexity is high; postpone. https://www.ogc.org/standards/geopackage/
- Buffer / route intersection existed in the asset subsystem; not worth adding as new Aereo endpoints before quality/deployment is complete.
- GeoTIFF, DEM, stockpile/terrain volume, AI insights, authentication overhaul, Redis/Celery and excessive styling: **out of scope**.

## 6. Git safety / milestone discipline

**Rule:** One phase = focused code diff + tests + exact review + commit + push to `origin/feature/aereo-geospatial-measurements` + tracker update. Never let uncommitted multi-phase work accumulate.

1. At each phase start: `git branch --show-current`, `git status --short`, `git log -1 --oneline`; expected branch is `feature/aereo-geospatial-measurements`.
2. Before applying a patch: `git apply --check <patch>`; only run `git apply <patch>` if check succeeds; never use `--reject`/`--force` blindly.
3. Stage **only reviewed paths**; `git diff --cached --stat` + `git diff --cached --check` + `git status --short`. Never accidentally commit `.env`, `.venv`, `node_modules`, `frontend/dist`, `.aereo/*.sqlite3`, logs, private keys or datasets with sensitive records.
4. Minimum gate: `python -m pytest aereo_tests -q` and `npm --prefix frontend run lint` and `npm --prefix frontend run build`, plus phase-specific smoke/test. Do **not** run destructive legacy test fixtures against an unconfirmed database.
5. Commit under user's own configured Git identity. Do not add assistant/co-author credit or rewrite previous Git history.
6. Push checkpoint immediately with `git push -u origin feature/aereo-geospatial-measurements` first time; later `git push`. Never force-push.
7. Record date, SHA, changed paths, tests, known failures, remaining work in `docs/AEREO_PHASE_TRACKER.md` for **every push**.
8. On regressions: first compare last known-good commit (`git log`, `git diff`) and selectively revert that phase via a new revert commit, not `git reset --hard` on shared work. Preserve any unrelated local changes.
9. Do not merge into `main` until all P0 gates and release acceptance pass. Final merge must be done from clean, current `main`; avoid copying arbitrary untracked work.

### Required checkpoint names and gates

| Phase | Suggested commit subject | Evidence before push |
| --- | --- | --- |
| **C0 — Existing working baseline** | `feat(aereo): checkpoint verified file measurement workspace` | 18 backend tests, lint/build, synthetic upload/map workflow, user screenshots |
| **C1 — External compatibility + hardening** | `test(aereo): validate independent gis fixtures and edge cases` | independent fixtures, CRS unit checks, upload caps, no regressions |
| **C2 — Quality and formats** | `feat(aereo): add survey quality reports and geojson kmz readers` | new tests for QA, GeoJSON/KMZ; mandatory formats unchanged |
| **C3 — Advanced results** | `feat(aereo): expose metric provenance and export APIs` | evidence metrics + CSV/GeoJSON contracts tested |
| **C4 — Reviewer UX** | `feat(aereo): integrate quality and evidence in geoinsight` | real backend data, full-row selection, build/lint, browser screenshot |
| **C5 — Container and cloud** | `build(aereo): package and verify persistent deployment` | docker build, live HTTP and restart tests; no ephemeral-only records |
| **C6 — Release candidate** | `docs(aereo): finalize reproducible assessment submission` | clean clone + CI + README + demo and documented limitations |

> These are **checkpoint names**, not claims that any commits already exist. If deployment constraints require reordering, prioritize C5 ahead of C2–C4 and record the decision in the tracker.

## 7. Verification matrix and quality gates

### Contract tests

- `[ ]` KML and Shapefile ZIP each POST 201 and GET metadata/measurement/GeoJSON; valid feature count, ID, geometry, properties, CRS.
- `[ ]` EPSG:4326 transformed into projected metric CRS, never degree-based measurement.
- `[ ]` Point `NOT_APPLICABLE`; 100×100m = 10,000m²; 3–4–5 line = 5m; hole polygon subtracts interior ring; multipart totals correct.
- `[ ]` `.prj` missing, malformed zip/XML, traversal, zip bomb, missing `.dbf`, invalid geometry and unsupported geometry handled gracefully.
- `[ ]` Result retrieval after server restart; metadata and feature status stable.

### Differentiator tests

- `[ ]` Valid and invalid feature mix yields deterministic per-feature QA report and accurate counts.
- `[ ]` GeoJSON RFC 7946 + KMZ accepted; invalid payloads rejected; required inputs unaffected.
- `[ ]` Perimeter, centroid, bbox and method metadata correct and units clear.
- `[ ]` CSV/GeoJSON exports are machine-readable and match API results.

### External data and benchmark evidence

- `[ ]` Download at least two appropriately licensed GIS datasets from external independent sources; archive source URL, dataset license, file name/hash, CRS, geometry counts and test result. Prefer a modest local-area dataset for metric validation, and use large/global datasets mainly for ingestion robustness.
- `[ ]` Test non-UTF-8 / `.cpg` DBF encodings where possible; nested ZIP paths, polygons with holes, multipart, projected feet and dateline cases. Document unsupported issues honestly.
- `[ ]` Benchmark 100/1,000-feature synthetic cases under limits; record time, memory and 4xx limit behavior. Do **not** extrapolate to enterprise/PB scale.
- `[ ]` Compare selected geographic measurements with an independent reference (e.g. pyproj.Geod/QGIS) and document projection methodology/tolerances. Beware projected-vs-geodesic differences.

### Deployment and review gates

- `[ ]` Backend isolated CI passes (SQLite test DB); frontend lint/build pass; npm audit production relevance reviewed.
- `[ ]` Docker production image builds, frontend `/geospatial`, `/docs` and API work under same public HTTPS origin; all required routes documented.
- `[ ]` Results persist in managed database after a redeploy/restart; API can process independent files over the **public network**.
- `[ ]` Public API upload limits and risk controls active; error text safe; no leaked private keys, real user data or diagnostic secrets.
- `[ ]` Reviewer opens link in a clean/private browser, uses sample and own file without registration, views result, gets QA report and export.
- `[ ]` GitHub default `main` contains verified code and release README; public repo accessible anonymously; final form submitted and confirmation captured before cutoff.

## 8. Schedule (IST) and scope cutoffs

| Time | Work | Gate |
| --- | --- | --- |
| **Fri 23:00–23:40** | Freeze, document and push currently working baseline C0; no new features | Known-good recovery SHA exists remotely |
| **Fri 23:40–Sat 02:00** | Independent GIS datasets, parser coverage, CRS tests, record issues | External-file risk understood |
| **Sat 07:00–10:00** | Survey QA reports and GeoJSON/KMZ, tests | Required endpoints still pass |
| **Sat 10:00–13:00** | **Deployment skeleton now**, Docker/app persistence and CI; deploy minimally working version | Public environment accessible |
| **Sat 13:00–16:00** | Perimeter/centroid/bbox, measurement provenance, summary/export APIs | Extra APIs demonstrably correct |
| **Sat 16:00–19:00** | Reviewer UI quality + report, test deployed integration | Product is usable end-to-end |
| **Sat 19:00–22:30** | Independent live uploads, performance/security audit, bug fixes, checkpoint pushes | No blockers outstanding |
| **Sun 07:00–10:00** | End-to-end regression / cold-start / browser checks, clean-clone reproducibility | Release gates green |
| **Sun 10:00–12:00** | README, architecture, test evidence, known limitations, demo video/screenshots | Reviewer package complete |
| **Sun 12:00–13:00** | Verified feature branch → main, public form link, final submit | **Submission confirmed** |
| **Sun 13:00–18:00** | Buffer / emergency fixes only. No scope additions. | No deadline gamble |

**Hard cutoffs:** If hosted P0 release is not stable by **Saturday 19:00**, stop adding optional file formats or extra metrics and focus on deployment. If the release is not stable by **Sunday 10:00**, freeze all enhancements and ensure reproducible GitHub/Docker/API submission. Regardless, complete form early: EOD hour is unspecified.

## 9. Known risks, mitigations and decisions

| Risk | Mitigation |
| --- | --- |
| Extra features break required `.kml`/`.zip` | Isolate parsers/adapters; regression tests every phase; rollback commit |
| Unrealistic area/length for world/polar/dateline geometry | Explicit CRS selection/caveats, independent reference checks; fail safely when reliable metric result cannot be established |
| Unknown CRS projected units | Never infer from raw coordinate magnitudes; require supplied CRS or indicate failure |
| Untrusted public uploads exhaust resources | Safe ZIP/XML, strict size/feature/vertex caps, rate/concurrency controls and deployment-side request limits |
| Browser map tile fails | Geometry-only key-free mode + independent data display; no key requirement |
| Uncontrolled multiuser public file history leaks data | Do not expose all uploads publicly without access controls; consider history browser-local or restrict list; document privacy design |
| PostgreSQL, DB schema or Docker conflict | Isolated Aereo tables/DB, verified test DB, no destructive migrations or volume removal |
| SQLAlchemy JSON result larger than hosting DB limits | Bound file size/features, record storage footprint and restart retrieval |
| npm vulnerabilities | Inspect `npm audit --omit=dev`, address exploitable prod cases without reckless `--force` upgrades |
| Cloud free-tier sleeps / ephemeral FS | Persistent external DB, documented cold-start expectations, retry/health, fallback reviewer Docker quickstart |
| Short time remaining / overbuilding | Scope gates and Saturday 19:00 enhancement cutoff; submit Sun 13:00 |

## 10. README and reviewer-delivery outline

1. Title: **Aereo Geospatial File Measurement API — GeoInsight** and 2-sentence domain pitch.
2. Exact assignment compliance table, followed by clearly labelled additional features.
3. **Live app**, **Swagger URL**, **GitHub URL**, demo video (only when verified); note hosting limits.
4. Architecture diagram + file flow (upload → validation → parsing → CRS → measurement → persistent store → API → Leaflet).
5. Local setup (Docker and/or simple SQLite dev), env vars, non-secret example values.
6. Sample `curl` upload; GET file info, measurements and GeoJSON/export; browser workflow.
7. Example real dataset and geometric output with tested units, warnings, geospatial accuracy caveats.
8. Tests/CI/benchmarks including commands, observed outputs and evidence, not broad unsupported claims.
9. Security considerations and API public limits.
10. Learning, design tradeoffs, known limitations, future scope and individual author information.

## 11. Future-chat continuation contract

For every subsequent coding/patch discussion, read this file and `docs/AEREO_PHASE_TRACKER.md` **first** and check user-provided current `git status`, `git log`, and test outputs. The repository files are the durable project memory. Do not rely on unverified chat recollections or automatically claim phases have passed.

At every handoff, report:

- current branch and exact last pushed SHA;
- phase completed, changed paths and test output;
- blockers and what remains;
- next **single** patch/milestone and its acceptance test;
- deadline risk and go/no-go decision.

**Final quality philosophy:** A working, correct, auditable required API plus one outstanding QA workflow is stronger than six unverified advanced features. No selection guarantee; maximize demonstrable engineering evidence.

# GeoInsight / Aereo — Phase Tracker and Recovery Log

**Owner:** Project repository maintainer
**Last updated:** 2026-10-09 after C0 source recovery
**Source of truth:** [AEREO_EXECUTION_MASTER_PLAN.md](./AEREO_EXECUTION_MASTER_PLAN.md).
**Submission target:** 2026-10-11 13:00 IST (internal target); hiring manager said 11 October EOD, exact time unknown.

## Current known state — read before coding

- [x] Aereo feature branch exists locally: `feature/aereo-geospatial-measurements` (shown by user).
- [x] Docker Engine/PostGIS checked healthy before feature development.
- [x] 18 Aereo Pytest tests passed locally on Windows; **do not assume they still pass after new patches**.
- [x] Existing frontend lint and production Vite build passed at earlier checkpoint.
- [x] Generated/synthetic KML & zipped Shapefile samples exercised end-to-end in browser; geometry selection, projected measurements, known square/hole/line checks matched expected results.
- [x] Browser screenshot demonstrated key-free geometry-only layer and restored row-click selection.
- [x] **C0 baseline committed and pushed**: `b52d4f8`; corrective engine-source commit pushed: `48c3a52`. User verified both engine files tracked and `18 passed`.
- [ ] External third-party GIS data tested.
- [ ] New formats, survey QA, extra metrics, enhanced exports implemented.
- [ ] Docker production deployment working, persistent results after restart.
- [ ] CI, security audit, final README, live smoke, GitHub main merge, form submission.

> Status is *evidence-based*: a checkmark means observed from supplied outputs, not a claim of full formal certification. No exact local commit SHA yet.

## Checkpoint record — append a row after every push

| Checkpoint | Date/time IST | Commit SHA | Test/build/QA evidence | Public branch status | Notes/issues |
| --- | --- | --- | --- | --- | --- |
| C0 — baseline | 2026-10-09 | `b52d4f8`, `48c3a52` | 18/18 Pytest, frontend lint/build passed; engine source corrective push verified | pushed `feature/aereo-geospatial-measurements` | Known good recovery SHA is `48c3a52` |
| C1 — external compatibility | PENDING | — | — | — | — |
| C2 — QA/formats | PENDING | — | — | — | — |
| C3 — measurement evidence/export | PENDING | — | — | — | — |
| C4 — reviewer UI | PENDING | — | — | — | — |
| C5 — Docker/cloud | PENDING | — | — | — | — |
| C6 — release | PENDING | — | — | — | — |

## At the start of each milestone

```powershell
git branch --show-current
git status --short
git log -1 --oneline
```

Before applying a patch:

```powershell
$patch = "$env:USERPROFILE\Downloads\YOUR_PATCH.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw "Patch check failed" }
git apply $patch
```

Run verification from **repo root**:

```powershell
python -m pytest aereo_tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Caution: legacy `tests/conftest.py` drops/creates tables in its configured database. Do **not** run broad legacy suites without confirming test database isolation.

After reviewing source + secrets + ignored files:

```powershell
git status --short
# Stage only reviewed paths for this phase, not blindly everything.
git diff --cached --stat
git diff --cached --check
git commit -m "<checkpoint message from master plan>"
git push -u origin feature/aereo-geospatial-measurements
# Later checkpoints can use: git push
git log -1 --oneline
```

**Do not run `git reset --hard`, `git clean -fd`, `docker compose down -v`, or `git push --force` to fix a failed patch.** Preserve other project containers and user data.

## Evidence log / open issues

- `2026-10-09`: Original static map had missing tile API key; geometry-only mode replaces it. Streets is optional best-effort.
- `2026-10-09`: Original project PostGIS functions include `ST_Area`, `ST_Length`, `ST_Centroid`, buffer, bbox, nearest, geofence, intersects. Aereo engine already supports MultiPolygon, MultiLineString, validity checks. No duplicate build.
- `2026-10-09`: Source QA fixtures are **generated**, not independently sourced geographic survey datasets; external data remains a release gate.
- `2026-10-09`: Npm reported 7 advisories (1 moderate, 6 high) before audit triage. Exact production risk still unknown.
- `2026-10-09`: As of this plan, no confirmed live deployment or form submission.

## Change decisions and blockers (append dated entries)

- `2026-10-09 / D01`: Keep existing repository; isolated standalone Aereo app and root `/geospatial` route.
- `2026-10-09 / D02`: Required KML and Shapefile first; GeoJSON and KMZ are high-value extras, but never at the cost of deployability.
- `2026-10-09 / D03`: Survey QA report, CRS provenance and interoperable export outrank buffers, AI, DEM/GeoTIFF, 3D volumes.
- `2026-10-09 / D04`: Push phase-wise; track checkpoint SHA + proof before advancing. Main branch updated only at release.

**At handoff to a new chat:** Share this file (or public repo link) and the latest `git status --short`, `git log -1 --oneline`, test results; resume from first pending checkpoint.

## C1 compatibility patch in progress (do not mark complete until pushed)

- Seven regression tests added covering nested/uppercase Shapefiles, CP1252 attributes, foot-based projection units, nested KML folders, impossible EPSG:4326 coordinates, feature cap and duplicate ZIP paths.
- Parser now refuses to render geometries whose transformed WGS84 bounds exceed valid longitude/latitude ranges.
- C1 acceptance: at least 25 isolated tests pass locally, one actual external Shapefile manually uploaded, browser workflow remains functional, commit and push recorded.
- External real-world GIS datasets are **NOT** automatically validated merely because the synthetic compatibility tests pass.

## 2026-10-10 — Verified recovery ledger (supersedes unchecked old boxes above)

- `70e0209`: C1 compatibility tests/source pushed; 25 tests passed. External Natural Earth river lines (13 features) processed; separate WGS84 geodesic comparison maximum deviation 0.208% for that dataset, not survey certification.
- `e5a33fd`: cross-platform npm lockfile repair pushed; GitHub CI subsequently recovered.
- `699c7ce`: single-origin Docker/React/FastAPI release pushed; 26 tests passed locally; user verified browser KML/Shapefile upload, GET/GeoJSON/measurements, health HTTP 200, and same stored ID after container restart.
- `85284b7`: feature isolation and provenance UI pushed; user screenshots show Point/LineString/Polygon selection and selected-only map.
- `e1de412`: updated dependency lockfile pushed. GitHub run `37979548065` **success**, both backend and frontend jobs successful, production audit **found 0 vulnerabilities**.
- **C2 in development (not pushed until verified):** add RFC 7946 GeoJSON/KMZ input, feature-level typed QA issues and `/api/files/{id}/quality/`; next run complete local and GitHub tests, then record new commit SHA. Do not confuse C2 with the earlier UI checkpoint label.
- **Not yet done:** public HTTPS deployment, C3 extended measurements/exports, C4 quality UI and full final README/submission. Prioritize a dependable submission ahead of speculative additions.

## 2026-10-10 — C2 verified browser/API acceptance and C3 implementation

- User validated 45/45 backend tests, React lint/build, a successful multi-stage Docker build and same-origin `/geospatial` HTTP 200.
- GeoJSON QA sample: 201 Created, 3 features, 1 measured, 1 `NOT_APPLICABLE`, 1 failed; `/quality/` reported `TRANSFORM_FAILED` for `bad-location` with correct counts.
- KMZ QA sample: 201 Created, 2 features, 1 measured, 1 `NOT_APPLICABLE`, 0 failed. Screenshots confirm map, source CRS, selected feature and SHA-256 provenance.
- The initial C2 frontend file chooser did not update the separate `geospatialService.js` extension validator; a focused fix was applied and verified before the above screenshots. C2 commit/push remains user-controlled; record SHA after push.
- C3 extends the same engine with polygon perimeter/centroid/WGS84 envelope, line parts/segments/endpoints, point coordinate evidence, `/summary/`, and CSV/GeoJSON `/export/`. Initial local tests in a C2-based patch workspace passed; user must rerun and commit/push C3 separately after C2.
- Outstanding: C4 visual quality explorer and server export UI, hosted service with durable DB and upload abuse protections, release README and submission.

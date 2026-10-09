# GeoInsight / Aereo — Phase Tracker and Recovery Log

**Owner:** Project repository maintainer
**Last prepared:** 2026-10-09 around 23:00 IST
**Source of truth:** [AEREO_EXECUTION_MASTER_PLAN.md](./AEREO_EXECUTION_MASTER_PLAN.md).
**Submission target:** 2026-10-11 13:00 IST (internal target); hiring manager said 11 October EOD, exact time unknown.

## Current known state — read before coding

- [x] Aereo feature branch exists locally: `feature/aereo-geospatial-measurements` (shown by user).
- [x] Docker Engine/PostGIS checked healthy before feature development.
- [x] 18 Aereo Pytest tests passed locally on Windows; **do not assume they still pass after new patches**.
- [x] Existing frontend lint and production Vite build passed at earlier checkpoint.
- [x] Generated/synthetic KML & zipped Shapefile samples exercised end-to-end in browser; geometry selection, projected measurements, known square/hole/line checks matched expected results.
- [x] Browser screenshot demonstrated key-free geometry-only layer and restored row-click selection.
- [ ] **C0 baseline committed and pushed**; SHA not yet available from user's terminal.
- [ ] External third-party GIS data tested.
- [ ] New formats, survey QA, extra metrics, enhanced exports implemented.
- [ ] Docker production deployment working, persistent results after restart.
- [ ] CI, security audit, final README, live smoke, GitHub main merge, form submission.

> Status is *evidence-based*: a checkmark means observed from supplied outputs, not a claim of full formal certification. No exact local commit SHA yet.

## Checkpoint record — append a row after every push

| Checkpoint | Date/time IST | Commit SHA | Test/build/QA evidence | Public branch status | Notes/issues |
| --- | --- | --- | --- | --- | --- |
| C0 — baseline | PENDING | PENDING | 18/18 Pytest + frontend lint/build observed precommit; rerun before staging | PENDING | Current working sources need reviewed staged diff |
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

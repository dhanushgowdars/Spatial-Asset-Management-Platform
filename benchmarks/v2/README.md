# GeoInsight V2 — realistic, deterministic local benchmark suite

**Scope:** Add-only tooling. No changes to API, frontend, tests, databases, Render or existing benchmark files.

**SAFETY:** All API clients reject targets other than `http://127.0.0.1:18130`. Only run with an isolated local SQLite benchmark DB; never run against your production Postgres database. Every successful upload adds a row containing full GIS results: periodically inspect the DB size, and stop the local Uvicorn service before manually removing a disposable benchmark DB. Never delete a DB without confirming its path and that it is only a benchmark DB. Generated fixtures, seeds, and CSV files are under `benchmarks/v2/output/` and gitignored.

## Dataset matrix (generated locally, not downloaded)

| Name | File | Contents | Oracle |
|---|---|---|---|
| medium_geojson | medium_250.geojson | 200 parcels + 50 routes, projected into WGS84 | 100×100m squares; 120m lines |
| large_geojson | large_1200.geojson | 960 parcels + 240 routes | Same known metrics |
| complex_geojson | complex_80.geojson | 20 polygons with holes, 20 multipart polygons, 40 curved dense lines | Independent Shapely projected metrics |
| medium_shapefile | medium_250.zip | 250 polygons with `.shp/.shx/.dbf/.prj` in EPSG:32643 | 10,000 m² each |
| medium_kml | medium_150.kml | 100 polygons, 25 lines, 25 points | Measured vs not applicable |
| medium_kmz | medium_150.kmz | One embedded KML with same 150 geometries | Same as KML |

Complex fixture polygons have hundreds of vertices. This suite deliberately stresses persistence of geometry-rich JSON, not just parsing trivial files. It does not simulate real customer data, and results on local SQLite are not PostgreSQL performance claims.

Measurements in the oracle are derived from the source UTM geometries **before** WGS84 conversion; the test compares them to the application's own computed measurements with a 0.02% tolerance (at least 0.25 metres or square metres). The preflight and seed verification check **all feature IDs and metric oracles**; repeated load requests check all statuses plus sampled first/middle/last metric values to avoid unnecessary Locust-side computation. `prepare.py` runs each fixture through the **real GeoInsight parsing engine**, independently of the API and DB.

## Prerequisites

From the isolated `GeoInsight-Hardening-Lab` workspace, on Windows PowerShell:

```powershell
Set-Location "D:\NEW VOLUME\CODING\PROJECTS\Backend Project\GeoInsight-Hardening-Lab"
& ".\.venv\Scripts\python.exe" -m pip check
& ".\.venv\Scripts\python.exe" benchmarks/v2/prepare.py
```

The preflight must finish with `PREFLIGHT PASSED` before any load tests.

Start your local API **in a separate terminal** (stop any server occupying port 18130 first):

```powershell
Set-Location "D:\NEW VOLUME\CODING\PROJECTS\Backend Project\GeoInsight-Hardening-Lab"
$env:AEREO_DATABASE_URL = "sqlite:///./.aereo/geoinsight-benchmark.sqlite3"
& ".\.venv\Scripts\python.exe" -m uvicorn aereo.api:app --host 127.0.0.1 --port 18130
```

This should be the already-running dedicated benchmark server. Verify its configuration before running load.

## Controlled test commands (second terminal)

**A. Medium files:** Start with 2 users, 30 seconds:

```powershell
& ".\.venv\Scripts\python.exe" -m locust -f benchmarks/v2/locust_realistic.py GeoInsightMediumUser --headless --users 2 --spawn-rate 1 --run-time 30s --stop-timeout 15 --host http://127.0.0.1:18130 --csv benchmarks/v2/output/medium_2users --only-summary
```

**B. Complex geometry:** If A succeeds, 1 user for 30 seconds:

```powershell
& ".\.venv\Scripts\python.exe" -m locust -f benchmarks/v2/locust_realistic.py GeoInsightComplexUser --headless --users 1 --spawn-rate 1 --run-time 30s --stop-timeout 15 --host http://127.0.0.1:18130 --csv benchmarks/v2/output/complex_1user --only-summary
```

**C. Large files:** If B succeeds, 1 user for 30 seconds (1,200 features per upload):

```powershell
& ".\.venv\Scripts\python.exe" -m locust -f benchmarks/v2/locust_realistic.py GeoInsightLargeUser --headless --users 1 --spawn-rate 1 --run-time 30s --stop-timeout 15 --host http://127.0.0.1:18130 --csv benchmarks/v2/output/large_1user --only-summary
```

**D. Read-only benchmark on seeded, verified datasets:** First seed one record per fixture, then run 2 users for 30 seconds:

```powershell
& ".\.venv\Scripts\python.exe" benchmarks/v2/seed_reads.py
& ".\.venv\Scripts\python.exe" -m locust -f benchmarks/v2/locust_realistic.py GeoInsightSeededReadUser --headless --users 2 --spawn-rate 1 --run-time 30s --stop-timeout 15 --host http://127.0.0.1:18130 --csv benchmarks/v2/output/seeded_reads_2users --only-summary
```

**Do not increase load or run multiple profiles simultaneously yet.** After each run, inspect error tables and server logs. This suite creates potentially large SQLite rows; it is intentionally staged.

## Interpreting results

- `POST [fixture]`: upload + GIS calculation + persistence (HTTP 201 and metadata validation).
- `VERIFY [fixture]`: retrieve full per-feature results and check count, all statuses, and independent sampled metric oracles. This is **not** included in POST latency.
- `GET [fixture]`: read-only retrieval of previously seeded files. No hidden setup uploads.
- Aggregate RPS combines POST and GET: compute **upload throughput separately** from POST rows.
- Locust `--run-time` limits the test duration; `--stop-timeout` can allow pending tasks to complete but does not certify a particular number of paired verification calls. Check POST and VERIFY counts.
- `0 errors` only means all executed requests passed. It is not a claim of maximum system capacity, and a successful low-user test does not establish scalability.
- Keep a machine/environment record (Python, Locust, hardware, isolated SQLite, single Uvicorn process, host, user count, runtime, fixture hashes) alongside result CSVs.

## Files

- `fixture_lib.py`: independent geometry generation, measurement oracles, validation and local-only guard.
- `prepare.py`: generates fixtures and validates each with actual `process_upload`, no DB access.
- `seed_reads.py`: safely persists and verifies one dataset of each kind on localhost.
- `locust_realistic.py`: four separate user profiles; all local-only.
- `output/`: generated datasets, fixture checksums, seeded IDs, result CSVs (ignored by Git).

No legacy `tests/` are executed. No Git push, deploy or application-code edit is performed by this package.

## Optional independent offline checks & CSV summary

These checks don't use your running server or a database:

```powershell
& ".\.venv\Scripts\python.exe" benchmarks/v2/smoke_checks.py
```

After any completed Locust run:

```powershell
& ".\.venv\Scripts\python.exe" benchmarks/v2/summarize.py benchmarks/v2/output/medium_2users_stats.csv
```

The CSV summary separates true upload throughput from aggregate requests/second.

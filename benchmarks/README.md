# GeoInsight local baseline benchmark v1

This is a **GET-workload baseline** with one synthetic KML upload per Locust user at setup time.
It targets ONLY `http://127.0.0.1:18130`. The script explicitly refuses other destinations.
No GIS application source files are changed by this package.

## Preconditions

- Open PowerShell in your separate `GeoInsight-Hardening-Lab` Git worktree.
- Run the local API on port 18130 with `AEREO_DATABASE_URL=sqlite:///./.aereo/geoinsight-benchmark.sqlite3`.
- Health: `http://127.0.0.1:18130/health` must return `healthy`.
- Run Locust with the lab `.venv` interpreter (Locust 2.46.7).
- Do not run tests against the production database or Render.

## First run: 3 simulated GET users, 30 seconds

```powershell
Set-Location 'D:\NEW VOLUME\CODING\PROJECTS\Backend Project\GeoInsight-Hardening-Lab'
& '.\.venv\Scripts\python.exe' -m locust -f benchmarks/locustfile.py GeoInsightReadUser `
  --headless --users 3 --spawn-rate 1 --run-time 30s `
  --host http://127.0.0.1:18130 `
  --csv benchmarks/results/read_baseline_3users --only-summary
```

Locust saves `read_baseline_3users_stats.csv`, `..._failures.csv` and other CSVs
into `benchmarks/results/`. The seeded KML files are *real* rows in the **local
SQLite benchmark DB**; no remote records are touched. They are deliberately
not deleted by benchmark scripts.

**Accuracy:** The tasks verify the file ID, 3 features, 2 measurable features,
non-zero area/length, point NOT_APPLICABLE, and summary totals. Any incorrect
payload is recorded as a request failure, even if the HTTP status is 200.

**Interpretation:** Exclude the separate `SETUP POST ...` row when comparing
GET throughput and latency. Report per-endpoint p50/p95 and errors; the
`Aggregated` row includes setup uploads and therefore is a mixed-workload total.
This run is for local SQLite only, not PostgreSQL/production performance claims.

## Later

After recording a baseline, compare another run with the same user count,
timings, interpreter, DB mode and fixture. Add separate bounded upload and
concurrent analysis workload scenarios in Phase 1B; they are NOT included here.
Do not increase users substantially before those safety tests are written.

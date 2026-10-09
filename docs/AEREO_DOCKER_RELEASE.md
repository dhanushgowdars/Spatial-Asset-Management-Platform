# C5 preparation — GeoInsight production Docker smoke

This builds **one image** that serves both the React `/geospatial` interface and the
existing Aereo API under the same origin. It does not run the legacy asset-management
API, does not overwrite its Docker Compose project, and does not expose the local
PostGIS database on any new port.

## 1. Build (repository root)

```powershell
docker build --file aereo/Dockerfile --tag geoinsight:release .
```

This runs `npm ci` on Linux using the committed lockfile and compiles React. A
failed build means **do not deploy**. The image keeps only production Python deps
and the generated frontend assets; your `.env` and `.aereo` directory are excluded.

## 2. Run isolated reviewer release locally

```powershell
docker run --rm --name geoinsight-preview -p 18140:8000 -v geoinsight-results:/data geoinsight:release
```

Then visit `http://localhost:18140/geospatial` and
`http://localhost:18140/docs`. In another terminal:

```powershell
Invoke-RestMethod http://localhost:18140/health
```

Use **both bundled sample datasets** from the page, then upload a separate manual
KML and a zipped Shapefile. Record a returned file ID. Stop the container with
Ctrl+C and start the same `docker run` command again. `GET
/api/files/<record-id>/measurements/` must still return the saved results.
The named Docker volume preserves data; `--rm` removes only the disposable
container, not its volume.

Port **18140** is intentionally different from existing development ports.
Do not run `docker volume rm geoinsight-results` unless you intend to delete
those preview records.

## 3. Hosted release

For a public deployment, configure `AEREO_DATABASE_URL` to a managed PostgreSQL
connection string, e.g. `postgresql+psycopg2://...` in the host's secret manager.
Do not use the default SQLite path on an ephemeral cloud filesystem. Deploy the
`feature/aereo-geospatial-measurements` branch only once security triage and live
checks pass; then merge verified code to `main` before submission.

This initial container does not yet provide application-level authentication or
rate limiting. Public upload exposure requires an explicit resource-abuse review,
file-size/feature-count validation, and hosting safeguards. A clean Docker build
alone does **not** establish that the service is production-ready.

## 4. Must-pass release gates

- Existing Aereo test suite passes (including `test_production.py`)
- React lint and production build pass on GitHub CI
- KML and Shapefile sample uploads work through the Docker-hosted browser UI
- Manual upload results agree with the REST API and map
- The same file ID remains retrievable after a container restart
- Live public HTTPS URL, database persistence and GitHub source are verified
- Dependency advisories are evaluated and addressed before public exposure

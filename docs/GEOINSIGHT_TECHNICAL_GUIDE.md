> **Archived GeoInsight reviewer introduction.** [Current assignment README](../README.md).

<!-- GEOINSIGHT_REVIEWER_LANDING_V1 -->
# GeoInsight — Geospatial File Measurement & Spatial Analysis

**Aereo internship assignment | FastAPI + React | Live, reproducible GIS measurements**

**[Open the live GeoInsight application](https://geoinsight-aereo.onrender.com/geospatial)** · **[REST API documentation](https://geoinsight-aereo.onrender.com/docs)** · **[Health check](https://geoinsight-aereo.onrender.com/health)**

> **Reviewer note:** This section documents the **GeoInsight Aereo assessment** deployed from the `feature/aereo-geospatial-measurements` branch. The earlier Spatial Asset Management Platform is a distinct legacy project in the same repository; its architecture and authentication claims do **not** describe the public GeoInsight assessment API.

## Assessment objective

Import KML or a zipped ESRI Shapefile, identify feature geometries and attributes, and calculate metric **polygon area (m²)** and **line length (m)** in an appropriate **projected CRS**. Preserve Point features without inventing area or length; report missing CRS, invalid coordinates and invalid geometries explicitly. Return inspectable results through a documented REST API.

The implementation also supports GeoJSON and KMZ, quality reporting, interactive maps, survey change detection, parcel topology checks, route/zone intersections and downloadable evidence.

## What to try (3-minute reviewer walkthrough)

| Step | Open | What to check |
| --- | --- | --- |
| 1 | [Measure](https://geoinsight-aereo.onrender.com/geospatial) | Upload the provided KML or zipped Shapefile sample; inspect polygon area, line length, source CRS and projected CRS. |
| 2 | [Survey quality](https://geoinsight-aereo.onrender.com/geospatial/quality) | Inspect successful polygons, non-applicable Points and failed invalid-coordinate records. |
| 3 | [Compare surveys](https://geoinsight-aereo.onrender.com/geospatial/compare) | Compare baseline/current polygon samples: approximately 5,000 m² each of added, removed and unchanged area. |
| 4 | [Topology](https://geoinsight-aereo.onrender.com/geospatial/topology) | Inspect overlapping parcels; optionally add a separate site-reference polygon to evaluate outside/uncovered area. |
| 5 | [Routes & zones](https://geoinsight-aereo.onrender.com/geospatial/routes) | Inspect a 140 m route crossing a zone: 40 m inside and 100 m outside. |
| 6 | [About & guide](https://geoinsight-aereo.onrender.com/geospatial/guide) | See supported formats, methods, limitations and reviewer guidance. |

The browser's bundled examples use the same live backend endpoints as manual file uploads; the displayed numbers are not hard-coded measurement results.

## Architecture and measurement flow

```text
KML / ZIP Shapefile / GeoJSON / KMZ
           |
     FastAPI validation
           |
   Geometry extraction + CRS
           |
  pyproj projection + Shapely
           |
  Metric area/length + QA/evidence
           |
  SQLAlchemy -> PostgreSQL (public deployment)
           |
   REST JSON / CSV / GeoJSON
           |
      React + Leaflet UI
```

- **Frontend:** React and Vite, Leaflet-based interactive mapping.
- **API:** Python 3.11, FastAPI, documented OpenAPI endpoints.
- **Spatial processing:** Shapely, pyproj and supporting vector-file readers; operations are computed in Python, **not PostGIS** for this assessment.
- **Persistence:** SQLAlchemy; PostgreSQL on Render for the public demonstration. Local Docker can use a named SQLite volume when no PostgreSQL URL is supplied.
- **Deployment:** Multi-stage `aereo/Dockerfile` builds React assets and serves frontend/API from one origin with Uvicorn.

**Coordinate-system distinction:** source files may use geographic coordinates such as `EPSG:4326`. Measurements use a suitable *local projected* metric CRS (for the known-size fixtures, `EPSG:32643`); map-ready GeoJSON is expressed in WGS84. Distortion and source-data quality still matter.

## Main API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/files/` | Multipart `file` upload (`.kml`, `.zip` Shapefile, `.geojson`, `.kmz`). |
| `GET` | `/api/files/{file_id}/` | Uploaded-file metadata. |
| `GET` | `/api/files/{file_id}/measurements/` | Feature-level geometry, CRS, measurement and status. |
| `GET` | `/api/files/{file_id}/quality/` | Validation findings and measurement eligibility. |
| `GET` | `/api/files/{file_id}/summary/` | Aggregated dataset summary. |
| `GET` | `/api/files/{file_id}/geojson/` | Map-ready GeoJSON. |
| `GET` | `/api/files/{file_id}/export/?format=csv` | Download CSV (or `format=geojson`). |
| `POST` | `/api/analysis/compare` | Two stored polygon datasets: added/removed/overlap. |
| `POST` | `/api/analysis/topology` | Survey overlap and optional reference boundary check. |
| `POST` | `/api/analysis/route-zones` | Stored route/zone intersection and inside/outside lengths. |
| `GET` | `/health` | Health check that also queries the database. |

Open the [interactive Swagger API docs](https://geoinsight-aereo.onrender.com/docs) for request bodies and response schemas.

### Example: upload from PowerShell

From the repository root, with the live demo URL:

```powershell
$base = 'https://geoinsight-aereo.onrender.com'
$sample = (Resolve-Path '.\frontend\public\samples\c4a_baseline.geojson').Path
$created = curl.exe -fsS -F "file=@$sample" "$base/api/files/" | ConvertFrom-Json
$created.id
Invoke-RestMethod "$base/api/files/$($created.id)/measurements/"
```

Expected for this synthetic 100 m × 100 m sample: **10,000 m²**, **400 m perimeter**, measured status, projected calculation CRS **EPSG:32643**.

## Run locally with Docker

From the repository root:

```powershell
docker build -f aereo/Dockerfile -t geoinsight:release .
docker run --name geoinsight-preview --rm -p 18140:8000 -v geoinsight-results:/data geoinsight:release
```

Open `http://localhost:18140/geospatial`, `http://localhost:18140/docs` and `http://localhost:18140/health`. For managed PostgreSQL, supply `AEREO_DATABASE_URL` securely via the hosting service's environment settings; **never commit connection URLs or credentials**.

## Verification evidence (11 October 2026)

- **81/81** Aereo backend pytest tests passed in the developer's environment.
- **14/14** frontend logic/presentation tests passed in the last reported local run; lint and Vite build passed.
- **37/37** live local API acceptance checks passed using known-size synthetic GIS fixtures, including KML, zipped Shapefile, KMZ, GeoJSON, CRS/QA, comparison, topology, route analysis and export parity.
- Public Render deployment served all **seven** tested page/documentation routes with HTTP 200, and `/health` returned `healthy`.
- Public GeoJSON upload reported `COMPLETED`; CSV exported **10,000 m²** and **400 m**, and the same persisted file ID remained retrievable **after a Render service restart**.
- See test cases in `aereo_tests/`, frontend test modules and included sample datasets. These are verification results for the tested fixtures, not a certificate of field-survey accuracy.

Commands:

```powershell
python -m pytest aereo_tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev --audit-level=high
```

## Scope, security and limitations

- **Public demonstration API:** The GeoInsight assessment endpoints do **not** implement account authentication, access control or application-level rate limiting. Do **not** upload confidential/private surveys. Uploaded result records are accessible using their file IDs. The older asset-management project's JWT/RBAC features do not protect this GeoInsight API.
- Input sizes are limited to **10 MiB** per upload and additional geometry limits are enforced. This is a portfolio/assessment deployment, **not** a multi-tenant production file service.
- Render's free web service can spin down when idle, causing cold-start delays. The free PostgreSQL database is short-lived (30-day expiry) and does not include managed backups.
- Measurements use 2D projected vector geometry. They do **not** provide certified cadastral boundaries, geodesic precision across large regions, raster/DEM processing, drone image reconstruction or enterprise load guarantees.
- Missing coordinate references, invalid geometries and projection issues should be reviewed via QA warnings rather than treated as measured observations.

## Design decisions and future work

A standalone Aereo API preserves the assessment's required endpoints without interfering with the original asset-management backend. Explicit projected-CRS metadata and source-record evidence make results inspectable. Follow-up production work would add authentication, per-user isolation, rate limiting, retention/deletion controls, background jobs, larger-data benchmarking and durable managed backups. Survey accuracy in operational use would require external field/GIS validation.

---

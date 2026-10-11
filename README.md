<!-- GEOINSIGHT_V2_LOCAL_REVIEW_README_V5: screenshots, phases, benchmark results and locally validated V2 -->
<div align="center">

# GeoInsight

### Geospatial File Measurement & Spatial Intelligence

**Aereo internship assignment · A working GIS API with an interactive reviewer workspace**

Upload geospatial files. Measure in the right coordinate system. Inspect *why* a result is valid. Compare survey boundaries, find overlaps, and analyse routes against zones.

[![Live application](https://img.shields.io/badge/OPEN_LIVE_APP-GEOINSIGHT-087f8c?style=for-the-badge)](https://geoinsight-aereo.onrender.com/geospatial)
[![API documentation](https://img.shields.io/badge/TRY_THE_API-SWAGGER-2563eb?style=for-the-badge)](https://geoinsight-aereo.onrender.com/docs)
[![CI](https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform/actions/workflows/aereo-ci.yml/badge.svg?branch=main)](https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform/actions/workflows/aereo-ci.yml)

### [🚀 Open the live GeoInsight workspace →](https://geoinsight-aereo.onrender.com/geospatial)

<sub>The links above point to the existing public submission. The V2 features and screenshots below were verified locally; public deployment of V2 is pending a separate release.</sub>

</div>

---

## Explore the live product

| Workspace | What a reviewer can do | Open |
| :--- | :--- | :--- |
| **01 — Measure** | Upload KML/Shapefile, inspect each geometry, CRS, area/length, map, and downloadable results | **[Launch measurement →](https://geoinsight-aereo.onrender.com/geospatial)** |
| **02 — Quality** | Review invalid geometries, unmeasurable Points, warnings and source evidence | [Open quality →](https://geoinsight-aereo.onrender.com/geospatial/quality) |
| **03 — Compare** | Overlay baseline and current polygon footprints; see added, removed and shared regions | [Compare surveys →](https://geoinsight-aereo.onrender.com/geospatial/compare) |
| **04 — Topology** | Find overlapping parcels and, with a reference boundary, uncovered/outside regions | [Inspect topology →](https://geoinsight-aereo.onrender.com/geospatial/topology) |
| **05 — Routes & zones** | Determine route length inside and outside survey/restricted polygons | [Analyse routes →](https://geoinsight-aereo.onrender.com/geospatial/routes) |
| **Guide** | Follow a walkthrough, learn the assumptions, and explore example scenarios | [Reviewer guide →](https://geoinsight-aereo.onrender.com/geospatial/guide) |

> [!TIP]
> **Start here (3 minutes):** **[Open GeoInsight Measure](https://geoinsight-aereo.onrender.com/geospatial)** → upload **your own KML, zipped ESRI Shapefile, GeoJSON or KMZ** → inspect the returned features, area/length (where applicable), source and measurement CRS, map, and downloadable results. Explore the other workspaces using your own compatible datasets, or test the three required endpoints in **[Swagger](https://geoinsight-aereo.onrender.com/docs)**. No provided example file is required. **Use public or synthetic data only**: this assessment demo does not have per-user access controls.

### A real measurement, not a mockup

[![GeoInsight live measurement results: 100 m by 100 m Shapefile polygon measured as 10,000 square metres](docs/images/geoinsight/01-measurement-results.png)](docs/images/geoinsight/01-measurement-results.png)

*Actual frontend capture from a synthetic 100 m × 100 m verification dataset · 1 successfully measured polygon · **10,000 m²** · EPSG:32643 · 0 failures. **[Upload your own survey file →](https://geoinsight-aereo.onrender.com/geospatial)**. Your results depend on your input.*

<details>
<summary><strong>Browse this README</strong></summary>

- [Real results: product showcase](#live-results--product-showcase)
- [Problem and solution](#the-problem-and-the-solution)
- [System architecture](#system-architecture)
- [V2 architecture and data flows](docs/GEOINSIGHT_V2_ARCHITECTURE.md)
- [Measurement pipeline and CRS](#how-geospatial-measurements-work)
- [Advanced spatial analyses](#spatial-intelligence-beyond-the-assignment)
- [Required API endpoints and examples](#api-reference--the-required-contract-first)
- [Technology and source layout](#technology-and-repository-layout)
- [Local setup and deployment](#run-locally)
- [Verified testing](#testing-and-reproducibility)
- [Design choices and limitations](#decisions-safeguards-and-limitations)

</details>

### What has been verified

| **160 / 160** | **4 / 4** | **Docker + PostgreSQL** | **Public submission** |
| :---: | :---: | :---: | :---: |
| V2 local Aereo backend tests passed | PDF polish tests passed locally | Production image, real upload/PDF and stored data after app restart verified locally | Previous deployed version; V2 not deployed yet |

The V2 counts above are from **local** October 2026 checks with synthetic reference data. The publicly linked Render service is the previous submission until an explicit V2 deployment. These checks are not a security audit, high-scale load test or certified land survey. See [testing and reproducibility](#testing-and-reproducibility).

### V2 development phases and verified outcomes (local release candidate)

V2 hardening was performed **only** in `GeoInsight-Hardening-Lab`; the original submitted checkout and current public Render deployment were not modified during these local checks. Each phase below is implemented and locally verified, subject to the test scope explained in the [verification record](docs/GEOINSIGHT_V2_VERIFICATION.md).

| Phase | Engineering change | Locally recorded evidence |
| --- | --- | --- |
| **1 — Baseline and realistic GIS workloads** | Deterministic GeoJSON, zipped Shapefile, KML and KMZ datasets; known-size oracle measurements; controlled Locust profiles | Medium **250 features**, large **1,200**, complex **80**, and format fixtures prepared. Low-concurrency baselines, not maximum throughput. |
| **2 — Upload reliability** | Database commit moved off the async upload loop; bounded concurrent upload work with explicit overload response | With upload limit **1**, six concurrent requests produced **one 201** and **five 503** responses; health/recovery remained available. |
| **3 — Request admission control** | In-memory per-peer upload rate limit (default **120/min**), bounded analyses (default **4**) | Verified **429** upload limit with `Retry-After` and **503** bounded analysis behavior. |
| **4 — Measured-results read optimization** | Bounded TTL/LRU read cache, ETags and conditional **304** replies for read endpoints | Local large-measurements GET p95 was **~380 ms** in a baseline sample and **~17 ms** in a warm-cache sample. Different short runs; do **not** interpret as a certified speedup. |
| **5 — Observability and reliability** | Request IDs, structured request logs, `Server-Timing`, error-path middleware coverage and regression tests | Request metadata verified for success and rejection paths; seven dedicated reliability regressions. |
| **6 — Verifiable decision evidence** | Persisted-results verification JSON, SHA-256 provenance, Survey Evidence Passport, and Survey Change Decision Brief | Known-size comparison: **5,000 m² added**, **5,000 m² removed**, **5,000 m² unchanged**, net **0 m²**, IoU **33.33%**. |
| **7 — Reviewer UX, PDF and production readiness** | 50-row browser pagination, selection-to-map focus, bounded PDF survey report, production Docker/PostgreSQL checks | **160/160** Aereo backend tests and **4/4** PDF polish tests; Docker upload/PDF passed; PostgreSQL record survived app restart. |

**Benchmark caution:** the earlier 73-request zero-failure read observation was a separate run; it is **not** the 62-request baseline or 72-request post-cache sample tabulated below. All numbers are synthetic local measurements with small sample sizes. The raw Locust CSVs are retained locally and are intentionally excluded from the Git release; no production SLO or certified speedup is claimed.

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


**Deep dive:** [V2 verification record: methods, observed results, tests and limitations](docs/GEOINSIGHT_V2_VERIFICATION.md).



---

## Live results — product showcase

These are **screenshots captured from the locally verified V2 React application** using synthetic test inputs. The backend generated the displayed values and map layers through real requests; these are not interface mockups. The linked public Render instance may still show the earlier submission until V2 is separately deployed. **Select an image to view the full-resolution capture.**

### 1. Inspect geometry and measurement provenance

[![GeoInsight Geometry Explorer with a synthetic mixed KML polygon, line and point rendered on a Leaflet street map](docs/images/geoinsight/02-geometry-explorer.png)](docs/images/geoinsight/02-geometry-explorer.png)

[![GeoInsight feature inspector showing a measured LineString, a not-applicable Point, source CRS and metric measurement CRS](docs/images/geoinsight/03-feature-inspection.png)](docs/images/geoinsight/03-feature-inspection.png)

The **map uses WGS84 for visualization**, while the feature inspector exposes the **projected measurement CRS, source record, geometry type, status and measured value**. The `mixed.kml` example includes a polygon, a measurable line and a Point correctly shown as not requiring area/length. Table selection animates the map and brings the selected geometry into view.

### 2. Compare two surveys — quantify what changed

[![Survey comparison metrics showing 10,000 square metre baseline and current footprints, and 5,000 each added, removed and shared](docs/images/geoinsight/04-survey-comparison-results.png)](docs/images/geoinsight/04-survey-comparison-results.png)

[![Survey comparison map displaying removed area in red, unchanged overlap in blue, and added area in green](docs/images/geoinsight/05-survey-comparison-map.png)](docs/images/geoinsight/05-survey-comparison-map.png)

This known-size verification scenario returns **5,000 m² added**, **5,000 m² removed**, and **5,000 m² unchanged**. Red, blue and green shapes are calculated difference and intersection geometries, not just colored numbers. **[Compare your own surveys →](https://geoinsight-aereo.onrender.com/geospatial/compare)**

#### V2 survey change decision brief

[![GeoInsight V2 decision brief identifying equal total area but different survey footprint, with 5,000 square metres each added, removed and shared](docs/images/geoinsight/09-survey-change-decision-brief.png)](docs/images/geoinsight/09-survey-change-decision-brief.png)

The V2 brief distinguishes **zero net area change** from **identical boundaries**, records the overlap ratio (**33.33%**), and offers an evidence-linked JSON decision brief. This is a derived comparison of synthetic known-size polygons, not a certified boundary determination.

<details>
<summary><strong>Inspect derived-overlay provenance (actual UI capture)</strong></summary>

[![Selected added-area feature with derived overlay status, 5,000 square metres and projected CRS](docs/images/geoinsight/06-survey-overlay-provenance.png)](docs/images/geoinsight/06-survey-overlay-provenance.png)

A derived result is explicitly marked as calculated overlay geometry and retains its CRS/method instead of being presented as an original survey record.

</details>

### 3. Evidence passport and mixed-geometry processing (V2)

[![GeoInsight V2 survey Evidence Passport summarizing mixed KML measurements and the Download Survey PDF and Verification JSON actions](docs/images/geoinsight/10-mixed-geometry-evidence.png)](docs/images/geoinsight/10-mixed-geometry-evidence.png)

The `mixed.kml` example extracts **three features**: a polygon, a line, and a Point. Exactly **two** require area/length measurement; the Point is explicitly **not applicable**. The **Survey Evidence Passport** summarizes status, warnings, CRS and uploaded-byte SHA-256, with downloadable JSON and a printable PDF built from stored results. PDF/JSON exports are evidence summaries, **not independent certification**.

### 4. Inspect a 250-feature synthetic workload (V2)

[![GeoInsight V2 measured 250 features with no failures, 2 square kilometres of summed polygon area and 6 kilometres of line length](docs/images/geoinsight/11-250-feature-evidence-passport.png)](docs/images/geoinsight/11-250-feature-evidence-passport.png)

<details>
<summary><strong>View the 250-feature map and five-page inspector</strong></summary>

[![GeoInsight V2 displays 200 polygon geometries and 50 LineStrings on its interactive geometry map](docs/images/geoinsight/12-250-feature-map.png)](docs/images/geoinsight/12-250-feature-map.png)

[![GeoInsight V2 paginated feature table showing page 5 of 5, with a 120 metre line selected for inspection](docs/images/geoinsight/13-250-feature-pagination.png)](docs/images/geoinsight/13-250-feature-pagination.png)

</details>

The synthetic workload contains **200 polygons × 10,000 m²** and **50 lines × 120 m** (2 km² *summed*, 6 km total). Pagination shows 50 rows per page **in the browser**, while map selection retains the full dataset. This is a functional workload demonstration, **not a maximum-capacity or concurrency benchmark**.

### 5. Measure a route crossing a zone

[![Routes and zones results reporting 1 route, 1 zone, 40 metres inside and 100 metres outside](docs/images/geoinsight/07-route-zone-results.png)](docs/images/geoinsight/07-route-zone-results.png)

[![Route-zone map showing navy full route, dashed amber restricted polygon and green inside-zone segment](docs/images/geoinsight/08-route-zone-map.png)](docs/images/geoinsight/08-route-zone-map.png)

In this verified scenario, a **140 m route** crosses a polygonal zone: **40 m inside** and **100 m outside**. The actual intersection geometry is calculated in a shared projected CRS and displayed as a separate map layer. **[Analyse your own routes and zones →](https://geoinsight-aereo.onrender.com/geospatial/routes)**

*Data note: these screenshots use synthetic reference geometry. They demonstrate working GIS processing but are not independent field-survey certification.*

---

## The problem and the solution

Geospatial data is not automatically measurable just because a map can display it. Survey files can contain geographic latitude/longitude coordinates (in **degrees**), unknown coordinate reference systems, malformed geometries, multipart features or conflicting parcel boundaries. Directly calculating planar distance or area on degree coordinates produces misleading units. Ignoring invalid records can make an apparently clean report difficult to defend.

**GeoInsight turns those files into inspectable, traceable measurements.** It reads the source geometry and attributes, validates each feature, chooses an appropriate *projected metric CRS*, calculates geometry measurements, preserves errors and provenance, and exposes the result through both an API and a map-based web interface.

**Primary assessment deliverable:** a FastAPI **Geospatial File Measurement API** handling KML and zipped ESRI Shapefiles with three required endpoints. The React interface, additional formats, QA, comparison, topology and route analysis are **implemented extensions**, not replacements for the requested API.

### At a glance

| Capability | Implementation |
| --- | --- |
| Supported uploads | **KML**, **zipped Shapefile** (required); GeoJSON and KMZ (additional) |
| Feature records | ID/index, geometry, type, properties, source CRS, status, warnings and evidence |
| Measurements | Polygon/MultiPolygon **area (m²)** and **perimeter (m)**; LineString/MultiLineString **length (m)** |
| Point behaviour | Preserve location and metadata; explicitly return **`NOT_APPLICABLE`** for area/length |
| CRS handling | **pyproj** converts coordinates to a suitable metric projection; **Shapely** calculates planar metrics |
| Data outputs | REST JSON, map-ready GeoJSON, CSV and GeoJSON downloads |
| Deployment | **React + FastAPI on one origin**, Docker on Render, PostgreSQL for persistent results |

### Aereo assessment requirements — traceable implementation

| Requirement | Where to verify |
| --- | --- |
| FastAPI backend; KML and zipped Shapefile upload | [`aereo/api.py`](aereo/api.py) · [`app/services/geospatial/engine.py`](app/services/geospatial/engine.py) |
| Feature ID/index, geometry type, geometry, CRS and attributes | [`GET /api/files/{id}/measurements/`](https://geoinsight-aereo.onrender.com/docs) · inspector screenshots above |
| Polygon area in m²; line length in m; Points retained without a fabricated metric | [Processing engine](app/services/geospatial/engine.py) · [measured examples](#how-geospatial-measurements-work) |
| Unsupported and invalid geometry handled safely | [Per-feature statuses](#geometry-decision-table) · [quality workspaces](https://geoinsight-aereo.onrender.com/geospatial/quality) |
| Transform geographic coordinates before measurement | [CRS explanation](#why-crs-selection-matters) · [`pyproj` processing](app/services/geospatial/engine.py) |
| Three required upload and retrieval endpoints | [API reference and sample requests](#api-reference--the-required-contract-first) |
| Public repository, setup, architecture, flow, choices, learning and next steps | This README · [isolated tests](aereo_tests/) · [supporting technical guide](docs/GEOINSIGHT_TECHNICAL_GUIDE.md) |

---

## System architecture

**V2 architecture (locally verified release candidate).** The public Render URL still serves the earlier submitted version until a controlled deployment. V2 retains the same **one-image, same-origin React + FastAPI** deployment model, but adds admission control, a bounded read cache, observability and evidence exports. The boxes below are logical components inside the **same application process**, not separate microservices.

```mermaid
flowchart TB
    USER["Reviewer / GIS engineer"] --> UI["React workspace + Leaflet<br/>measure / quality / compare / topology / routes"]
    subgraph APP["GeoInsight V2 · one Docker image · Uvicorn / FastAPI"]
        STATIC["production.py<br/>Serve compiled Vite frontend"]
        TRACE["Request telemetry<br/>X-Request-ID · Server-Timing · structured logs"]
        API["api.py<br/>REST routes + DB sessions"]
        RATE["Upload rate limit<br/>per-peer, process-local · 429"]
        UP["Bounded upload processing<br/>503 on overload · threaded DB write"]
        GIS["GIS engine<br/>parse + validate · pyproj + Shapely"]
        READ["GET measurements / GeoJSON<br/>bounded TTL/LRU cache · ETag / 304"]
        ANALYSIS["Bounded spatial analyses<br/>compare / topology / route-zone"]
        EVIDENCE["Evidence and exports<br/>verification JSON · ReportLab PDF · CSV"]
        ORM["SQLAlchemy<br/>file metadata + persisted result JSON"]
    end
    DB[("Database<br/>SQLite local · PostgreSQL validated")]
    UI -->|"Frontend routes + assets"| STATIC
    UI -->|"Same-origin API requests"| TRACE
    TRACE --> API
    API --> RATE
    RATE --> UP
    UP --> GIS
    GIS --> ORM
    API --> READ
    READ --> ORM
    API --> ANALYSIS
    ANALYSIS --> GIS
    ANALYSIS --> ORM
    API --> EVIDENCE
    EVIDENCE --> ORM
    ORM <--> DB
    classDef ui fill:#e8f3fd,stroke:#2670a6,color:#173a56
    classDef work fill:#e8f6f1,stroke:#1c826c,color:#16493c
    classDef db fill:#fff0dc,stroke:#b67b38,color:#6a451c
    class USER,UI,STATIC ui
    class TRACE,API,RATE,UP,GIS,READ,ANALYSIS,EVIDENCE work
    class ORM,DB db
```

The in-memory upload rate limiter and cache are **per-process**, not Redis or shared services. The frontend's 50-row pagination is **client-side**: the measurements API still returns the complete saved feature list. New verification JSON and PDF reports are views of the same **persisted** processing results; they do not independently recalculate geometry or certify land boundaries. SQLAlchemy stores records; **Shapely + pyproj** do the GIS computations, not PostGIS SQL.

For a component inventory, trust boundaries, cache/admission semantics and additional data-flow diagrams, see **[V2 architecture and data flows](docs/GEOINSIGHT_V2_ARCHITECTURE.md)**. For benchmark methods and the seven-phase results, see the **[V2 verification record](docs/GEOINSIGHT_V2_VERIFICATION.md)**.

### Upload-to-evidence sequence (V2)

```mermaid
sequenceDiagram
    autonumber
    actor R as Reviewer
    participant UI as React workspace
    participant API as FastAPI (request telemetry)
    participant GATE as Upload rate and capacity controls
    participant GIS as GIS engine (Shapely + pyproj)
    participant DB as SQLAlchemy / database
    participant OUT as Verification JSON / PDF renderer
    R->>UI: Select KML, ZIP Shapefile, GeoJSON or KMZ
    UI->>API: POST /api/files/ (multipart field: file)
    API->>GATE: Check per-peer rate + bounded upload capacity
    alt Rejected on rate or capacity
        GATE-->>UI: 429 or 503, with Retry-After
    else Admitted
        GATE->>GIS: Parse, validate, project, measure
        GIS-->>GATE: Features, CRS, results, diagnostics
        GATE->>DB: Commit metadata + result JSON (off event loop)
        DB-->>GATE: Saved file ID
        GATE-->>UI: 201 Created + file ID
    end
    UI->>API: GET /api/files/{id}/measurements/
    Note over API,DB: Bounded process-local cache; ETag + conditional 304 on cached reads
    API-->>UI: Feature measurements or 304 Not Modified
    R->>UI: Request verification PDF
    UI->>API: GET /api/files/{id}/verification-report.pdf
    API->>DB: Load stored results and SHA-256 provenance
    DB-->>API: Persisted record
    API->>OUT: Build bounded printable evidence (no re-measurement)
    OUT-->>UI: PDF attachment (application/pdf)
    UI-->>R: Readable survey report + documented limitations
```

For **survey comparison**, a separate request reads *two persisted survey IDs*, computes their deterministic polygon difference/intersection using the existing spatial-intelligence module, and presents the derived shapes and Survey Change Decision Brief. Equal net area does **not** imply identical boundaries.

---

## How geospatial measurements work

```mermaid
flowchart TD
    A([Upload file]) --> B{"Supported type<br/>and ≤ 10 MiB?"}
    B -->|No| X["Reject request<br/>HTTP 413 / 415"]
    B -->|Yes| C["Safely parse KML / SHP ZIP<br/>GeoJSON / KMZ"]
    C --> D["Extract ID, index, attributes,<br/>geometry and source CRS"]
    D --> E{"Valid feature<br/>and known CRS?"}
    E -->|No| F["FAILED · explain issue"]
    E -->|Yes| G{"Geometry type?"}
    G -->|"Point / MultiPoint"| P["NOT_APPLICABLE<br/>preserve point coordinates"]
    G -->|"Other unsupported"| U["UNSUPPORTED<br/>explain limitation"]
    G -->|"Polygon / LineString families"| H["Convert for display to WGS84<br/>select measurement CRS"]
    H --> I["pyproj transforms coordinates<br/>to metric projection"]
    I --> J["Shapely area or length<br/>+ perimeter/segment evidence"]
    J --> K["MEASURED · units, method, CRS"]
    F --> L["Persist all feature statuses<br/>and dataset record"]
    P --> L
    U --> L
    K --> L
    L --> M(["Retrieve JSON · QA · map GeoJSON · CSV"])

    classDef good fill:#E4F5EF,stroke:#13765C,color:#134938
    classDef caution fill:#FFF2DF,stroke:#BE7B24,color:#59350B
    classDef stage fill:#EDF3FF,stroke:#557FD0,color:#173967
    class K,M good
    class F,U,X caution
    class C,D,H,I,J,L stage
```

1. **Validate the uploaded dataset.** Check file type, nonempty content and the **10 MiB** upload limit. Archive handling additionally rejects unsafe paths and enforces limits on expanded size and file counts.
2. **Extract source evidence.** Parse KML Placemarks, required Shapefile components (`.shp`, `.shx`, `.dbf`, optional `.prj`), GeoJSON Features or KMZ KML. Preserve per-feature index, ID, type, attributes and original CRS.
3. **Validate per feature.** Unreadable/invalid geometry, missing Shapefile CRS, coordinate and transformation errors become `FAILED` records with diagnostic detail. Points remain inspectable without invented area/length.
4. **Choose a metric CRS.** Use WGS84 for browser geometry and a suitable projected CRS for each measurable feature; retain both CRS labels in the result.
5. **Calculate and attach evidence.** Use planar projected geometry for area/length, plus polygon perimeter/centroid or line-part/segment details. Preserve warnings, method and measurement units.
6. **Persist and expose results.** Store metadata and structured results; retrieve them by the generated file ID, download CSV/GeoJSON or supply IDs to later spatial analyses.

An HTTP **201 Created** means the upload was accepted and persisted; it does **not** mean every feature was measurable. A dataset may be `COMPLETED_WITH_ERRORS`. Always check individual statuses.

### Geometry decision table

| Geometry | Metric result | Status |
| --- | --- | --- |
| `Polygon`, `MultiPolygon` | Area **m²**, perimeter evidence **m** | `MEASURED` if valid |
| `LineString`, `MultiLineString` | Length **m**, segment evidence | `MEASURED` if valid |
| `Point`, `MultiPoint` | Location retained; no area/length | `NOT_APPLICABLE` |
| Other unsupported geometry | No fabricated measurement; reason retained | `UNSUPPORTED` |
| Invalid geometry / missing CRS / bad transform | Diagnostic and error evidence | `FAILED` |

### Why CRS selection matters

**EPSG:4326 longitude/latitude coordinates are angular degrees, not metres.** Computing Shapely `.area` or `.length` on unprojected degrees does not answer an area/length-in-metres question.

| Situation | Implemented measurement rule |
| --- | --- |
| Local geometry within supported UTM latitude/extent bounds | Pick UTM zone from location (`EPSG:326xx` north / `EPSG:327xx` south) |
| Large/polar polygon | Locally centred Lambert azimuthal equal-area (LAEA), with a caveat |
| Large/polar line | Locally centred azimuthal equidistant (AEQD), with a caveat |
| Missing/unknown source CRS (for example, Shapefile without usable `.prj`) | Fail the measurement rather than guessing coordinates |
| Display geometry and overlays | WGS84 coordinates for web-map interoperability |

The implemented method is **2D projected planar geometry**, not a geodesic/terrain or survey-certification engine. Projection distortion, bad source coordinates and elevations can still affect real-world accuracy.

### Worked example — a known-size square

For reproducibility, the displayed verification run used a synthetic **100 m × 100 m** polygon in a zipped Shapefile. In the screenshot, its **source and measurement CRS are both EPSG:32643** (UTM zone 43N). This is **one test case, not a required file or a fixed result for other uploads**. The verified measurement is:

| Field | Result |
| --- | ---: |
| Projected polygon area | **10,000 m²** |
| Projected polygon perimeter | **400 m** |
| Source CRS | `EPSG:32643` (projected UTM 43N) |
| Selected metric CRS | `EPSG:32643` (UTM zone 43N) |
| Status | `MEASURED` |
| Method | `projected_planar_geometry` |

**The result is accompanied by the source feature, CRS labels, unit, WGS84 bounds, polygon-part count and centroid evidence**, rather than only a standalone number. Values are from synthetic fixtures and are not a claim of certified field accuracy.

---

## Spatial intelligence beyond the assignment

These tools reuse *stored dataset IDs*. They do not calculate results from hard-coded React values.

| Analysis | Operation | Output and verified example |
| --- | --- | --- |
| **Survey quality** | Classify measured, not applicable and failed features; explain issues | Demo fixture: **3 features** → 1 measured, 1 Point not applicable, 1 failed |
| **Survey comparison** | Union baseline/current polygons; compute intersections/differences in a common local metric CRS | Shifted-square fixture: ~**5,000 m²** each added, removed and overlapping; ~**33.33% IoU** |
| **Parcel topology** | Compare parcel polygons pairwise; optionally compare survey union against an independent reference boundary | Fixture: **1 overlap**, ~**5,000 m²** |
| **Routes & zones** | Intersect route geometry with the union of zone polygons to avoid double-counting | Fixture: **140 m** route → **40 m inside**, **100 m outside** |

### Spatial overlay logic

```mermaid
flowchart LR
    subgraph INPUT["Persisted survey datasets"]
        BASE[Baseline polygons]
        CURR[Current polygons]
        PARCEL[Survey parcels]
        ROUTE[Line routes]
        ZONE[Polygon zones]
    end
    PROJECT["Common local metric CRS<br/>pyproj"]
    BASE --> PROJECT
    CURR --> PROJECT
    PARCEL --> PROJECT
    ROUTE --> PROJECT
    ZONE --> PROJECT
    PROJECT --> COMP["Compare: intersection / difference"]
    PROJECT --> TOPO["Topology: pairwise overlap<br/>optional reference boundary"]
    PROJECT --> CLIP["Routes: line ∩ zone union"]
    COMP --> MAP["Metric summaries +<br/>GeoJSON map overlays"]
    TOPO --> MAP
    CLIP --> MAP
```

**Important topology distinction:** an overlap can be calculated from the submitted parcels alone. An *uncovered area* or *outside-reference area* can only be assessed when a separate reference boundary is supplied. GeoInsight does not mistake a missing reference for “zero gaps.” Large/complex studies have additional feature, geometry and geographic-extent limits.

---

## API reference — the required contract first

**Base URL:** [`https://geoinsight-aereo.onrender.com`](https://geoinsight-aereo.onrender.com)

**Interactive OpenAPI:** **[Try requests in Swagger →](https://geoinsight-aereo.onrender.com/docs)**

### Required by Aereo

| Method | Endpoint | Response |
| --- | --- | --- |
| **`POST`** | **`/api/files/`** | `201` — process `multipart/form-data` field `file`; return file ID, metadata and resource URLs |
| **`GET`** | **`/api/files/{id}/`** | Stored file metadata: name, source CRS, hash, counts, status |
| **`GET`** | **`/api/files/{id}/measurements/`** | All feature records: geometry, CRS, attributes, metric measurement, warnings and evidence |

### Additional endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/files/{id}/quality/` | Feature-level QA and dataset diagnostics |
| `GET` | `/api/files/{id}/summary/` | Aggregate results and geometry counts |
| `GET` | `/api/files/{id}/geojson/` | WGS84 GeoJSON for inspection/maps |
| `GET` | `/api/files/{id}/verification-report/` | V2 persisted-results verification JSON, source SHA-256, CRS and limitations |
| `GET` | `/api/files/{id}/verification-report.pdf` | V2 downloadable PDF survey summary and bounded feature appendix |
| `GET` | `/api/files/{id}/export/?format=csv` | Download CSV; supports `format=geojson` |
| `POST` | `/api/analysis/compare` | `{ "baseline_file_id": "…", "current_file_id": "…" }` |
| `POST` | `/api/analysis/topology` | `{ "file_id": "…", "reference_file_id": "…" }` (reference optional) |
| `POST` | `/api/analysis/route-zones` | `{ "route_file_id": "…", "zone_file_id": "…" }` |
| `GET` | `/health` | Database-aware readiness check |
| `GET` | `/docs` | Swagger UI |

### Copy, run, inspect (PowerShell)

Use a **local file of your choice** (`.kml`, `.zip` containing an ESRI Shapefile, `.geojson`, or `.kmz`). The following commands prompt for its full path, upload it to the public assessment API, then retrieve the actual results. **Do not upload confidential or personal survey data.**

```powershell
$base = "https://geoinsight-aereo.onrender.com"
$filePath = (Read-Host "Full path to your KML, zipped Shapefile, GeoJSON or KMZ file").Trim('"')
if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) { throw "File not found: $filePath" }

# Upload the file you selected; .kml and zipped Shapefile are the required formats.
$response = curl.exe -fsS -F "file=@$filePath" "$base/api/files/" | ConvertFrom-Json
$id = $response.id
$response | Format-List id, filename, status, feature_count, successful_measurements

# Retrieve the two mandatory GET resources.
Invoke-RestMethod "$base/api/files/$id/" | Format-List
$results = Invoke-RestMethod "$base/api/files/$id/measurements/"
$results.measurements | Select-Object id, geometry_type, crs, measurement_crs, status, measurement
```

Use the same steps for **any supported upload type**. The returned file ID and measurements depend on your input; the API generates a new ID for each upload.

<details>
<summary><strong>Example response shape (illustrative, abbreviated)</strong></summary>

```json
{
  "file_id": "<generated-32-character-id>",
  "filename": "survey.geojson",
  "crs": "EPSG:4326",
  "feature_count": 1,
  "status": "COMPLETED",
  "measurements": [
    {
      "id": "example-square",
      "index": 0,
      "geometry_type": "Polygon",
      "crs": "EPSG:4326",
      "measurement_crs": "EPSG:32643",
      "status": "MEASURED",
      "measurement_method": "projected_planar_geometry",
      "measurement": { "type": "area", "value": 10000.0, "unit": "m2" },
      "evidence": { "perimeter_m": 400.0 }
    }
  ]
}
```

This is a deliberately simplified representation of `GET /api/files/{id}/measurements/`, **not** a verbatim live response. Full records also include source geometry, properties and issues.

</details>

### Export or analyse your saved data

```powershell
# Export a real server-generated CSV and GeoJSON file.
curl.exe -fLsS "$base/api/files/$id/export/?format=csv" -o "geoinsight-results.csv"
curl.exe -fLsS "$base/api/files/$id/export/?format=geojson" -o "geoinsight-results.geojson"

# Quality report and aggregate summary.
Invoke-RestMethod "$base/api/files/$id/quality/"
Invoke-RestMethod "$base/api/files/$id/summary/"
```

To compare **your own two compatible polygon surveys**, upload each file using the **Measure** or **Compare** interface (or `POST /api/files/`), then supply the two returned IDs:

```powershell
$body = @{ baseline_file_id = "<baseline-id>"; current_file_id = "<current-id>" } | ConvertTo-Json
Invoke-RestMethod -Method Post "$base/api/analysis/compare" -ContentType "application/json" -Body $body
```

**HTTP errors:** unsupported file extension `415`; oversized/empty upload `413`; invalid file/analysis `422`; missing ID `404`; storage/database problems `503`. An accepted file can still contain per-feature `FAILED` records; always review status and diagnostics.

---

## Technology and repository layout

| Layer | Technology | Role |
| --- | --- | --- |
| API | **Python 3.11 · FastAPI · Pydantic** | Uploads, contracts, OpenAPI, validation |
| GIS | **Shapely · pyproj · PyShp · safe XML/ZIP parsing** | Extract, transform and measure vector geometry |
| Data | **SQLAlchemy · PostgreSQL** (hosted), **SQLite** (local preview) | Persist feature results and metadata |
| UI | **React · Vite · React Router** | File upload, analysis workspaces and navigation |
| Maps | **Leaflet · React Leaflet** | Vector display, overlays and feature inspection |
| Release | **Docker · Uvicorn · Render** | One-origin deploy of static React assets and FastAPI |
| Verification | **pytest · Node tests · ESLint · Vite · GitHub Actions** | Regression, lint and production-build checks |

```text
Spatial-Asset-Management-Platform/
├── README.md                           ← this GeoInsight assessment guide
├── aereo/
│   ├── api.py                          ← REST APIs / SQLAlchemy persistence
│   ├── production.py                   ← one-origin React + FastAPI host
│   └── Dockerfile                      ← multi-stage production image
├── app/services/geospatial/
│   ├── engine.py                       ← parsing, CRS and measurements
│   ├── quality.py                      ← QA rules and diagnostics
│   ├── reporting.py                    ← summary, CSV and GeoJSON
│   └── spatial_intelligence.py         ← compare, topology, route/zone
├── frontend/src/pages/
│   ├── Geospatial/                     ← measurement workspace
│   ├── SpatialIntelligence/            ← QA, compare, topology, routes
│   └── GeoGuide/                       ← reviewer documentation
├── frontend/public/samples/           ← browser demo datasets
├── aereo_samples/                     ← synthetic GIS fixtures
├── aereo_tests/                       ← isolated backend/API tests
├── docs/
│   ├── GEOINSIGHT_TECHNICAL_GUIDE.md
│   └── SPATIAL_ASSET_MANAGEMENT_PLATFORM.md
├── aereo-requirements.txt
├── requirements.txt
└── .github/workflows/aereo-ci.yml
```

The GeoInsight implementation spans several folders in a repository that also has an older application; **`aereo/` alone is not a runnable standalone export**.

---

## Run locally

### Option A · Full app (recommended)

Docker builds the real React frontend and the Python API together. Run these from a clean clone:

```powershell
git clone https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform.git
cd Spatial-Asset-Management-Platform

docker build -f aereo/Dockerfile -t geoinsight:release .
docker run --rm --name geoinsight-preview -p 18140:8000 `
  -v geoinsight-results:/data geoinsight:release
```

Open **[http://localhost:18140/geospatial](http://localhost:18140/geospatial)** for the app, `http://localhost:18140/docs` for Swagger, and `http://localhost:18140/health` for database-aware health. The local preview uses SQLite at `/data/measurements.sqlite3` in the **named Docker volume**. Stopping the container does not erase the volume.

### Option B · Python API only

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r aereo-requirements.txt
uvicorn aereo.api:app --host 127.0.0.1 --port 18130
```

Swagger is at `http://127.0.0.1:18130/docs`. Without `AEREO_DATABASE_URL`, the API uses local SQLite under `.aereo/`. Use the Docker method to reproduce the public frontend/API integration.

### Deployed environment

| Item | Live configuration |
| --- | --- |
| Deployment URL | **[GeoInsight /geospatial](https://geoinsight-aereo.onrender.com/geospatial)** |
| Build | `aereo/Dockerfile`, build context `.` |
| Runtime | FastAPI factory `aereo.production:create_production_app`, Uvicorn port **8000** |
| Hosting | Render free web service; React and API on one HTTPS origin |
| Persistence | Render PostgreSQL, connected by private `AEREO_DATABASE_URL` environment variable |
| Health | [`/health`](https://geoinsight-aereo.onrender.com/health) checks database availability |

**No credentials or database connection strings are included in this repository guide.** Do not upload private/customer survey datasets to the unauthenticated public demo. Render free services can spin down, and the free database has short-lived retention; this is an assessment deployment, not permanent storage.

---

## Testing and reproducibility

The previous public submission was verified with **synthetic known-size geometry** and API/CI checks. Separately, the V2 hardening worktree passed **160/160 local Aereo backend regression tests** and **4/4 PDF polish tests**; local frontend ESLint and Vite build passed. The V2 production Docker image served five checked HTTP routes, handled a real Shapefile upload and generated a PDF. A separate PostgreSQL 16 container retained the 10,000 m² stored result after an **application-container restart** (the database container stayed running). The PDF formatting polish was applied **after** that Docker image build and therefore still requires a final image rebuild and live smoke test. The new V2 screenshots represent this local release candidate, not the currently deployed public service.

| Check | Recorded verification |
| --- | --- |
| Isolated Aereo backend suite | **V2 local 160 / 160 passed**; original public submission previously reported 81 / 81 |
| Frontend logic/presentation tests | Original submission **14/14** reported; V2 component-level pagination, decision-brief and Evidence Passport tests also passed in separate local runs (not asserted as one aggregate total) |
| Real local HTTP acceptance suite | Original submission **37/37**; V2 additional HTTP 200/304/404/429/503, PDF and health probes passed locally |
| Frontend lint and production build | Passed in local V2 worktree before final release audit |
| Public reviewer routes | **7 / 7** checked routes returned HTTP 200 |
| Cloud health | `{"status":"healthy"}` |
| Cloud data persistence | Original public submission retained its stored record; separately, V2 **local PostgreSQL 16** retained file data after application-container restart |
| GitHub Actions | **Both API regression and React lint/build jobs passed** on `1bba33f` for the [feature branch](https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform/actions/runs/38122862336) **and** [main](https://github.com/dhanushgowdars/Spatial-Asset-Management-Platform/actions/runs/38123212462) |

The visible regression evidence is **test evidence**, not certified land-survey precision, security audit or load test. The current CI runs isolated Aereo backend tests plus a frontend contract test, lint and build; the larger local frontend tests are not all part of the CI workflow.

Run the isolated checks (the **V2** local worktree should use its explicit `.venv` interpreter for Python checks, and should never run the legacy root-level pytest suite):

```powershell
python -m pytest aereo_tests -q
node --test frontend/src/pages/SpatialIntelligence/demoContracts.test.mjs `
  frontend/src/pages/SpatialIntelligence/derivedProvenance.test.mjs `
  frontend/src/pages/SpatialIntelligence/presentation.test.mjs
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
```

> [!CAUTION]
> The repository's *older* `tests/conftest.py` can drop/recreate tables in its configured **test** database. Do not run indiscriminate legacy tests or database migrations without proving isolation. The Aereo assessment suite is explicitly in [`aereo_tests/`](aereo_tests/).

### What is tested

- Required KML and zipped-Shapefile parsing; optional GeoJSON/KMZ; multipart geometries and attributes.
- Valid projected area/length, polygon perimeter and centroid, line evidence, Point non-applicability, malformed data and unknown CRS.
- Archive-safety checks, bounded inputs, per-feature QA and partial-failure reporting.
- CSV/GeoJSON outputs, persisted API contracts, overlay comparisons, topology reference semantics and route/zone length conservation.
- Production SPA deep links and CI frontend lint/build compatibility.

For verification methodology and automated coverage, see the **[Aereo regression tests](aereo_tests/)**. Synthetic fixtures in the repository support reproducibility; they are optional and not required to operate the API.

---

## Decisions, safeguards and limitations

| Design decision | Why it matters |
| --- | --- |
| **Keep the required FastAPI API independent** | Delivers the exact assignment contract without activating the older authentication/PostGIS application |
| **Project before measuring** | Avoids interpreting geographic degrees as metres; exposes the selected CRS and planar method |
| **Return per-feature evidence and status** | Helps reviewers distinguish measurable, inapplicable and failed geometry instead of hiding bad input |
| **Use deterministic geometry overlays** | Survey comparison, topology and route-zone analysis are explainable Shapely calculations |
| **Use persisted IDs and one-origin hosting** | Frontend and API analyse the same saved records; PostgreSQL survives a web-service restart |
| **Bound uploaded data** | 10 MiB upload limit, archive checks and geometry/feature limits help contain malformed inputs |

**Boundaries of this release:**

- The **publicly deployed submission** has **no authentication, per-user isolation or rate limiting**. The **locally tested V2** adds in-memory, per-peer upload rate limiting, bounded upload/analysis admission control, a bounded read cache with ETags, and request timing/IDs, but these safeguards do **not** replace authentication or user isolation and were **not deployed** at the time of this local screenshot review. Use public/synthetic data only; knowing a stored ID enables retrieval. Uploaded-result retention/deletion is not managed for end users.
- Limits include 10 MiB compressed uploads, up to 5,000 features per upload and tighter limits for complex overlays. Inputs exceeding those boundaries can be rejected.
- Metrics are **2D projected planar** results; not certified cadastral, geodesic over continental extents, elevation-aware, raster/DEM or photogrammetric reconstructions.
- The free Render deployment may cold-start and its free PostgreSQL offering is temporary (30-day lifetime in the configured assessment plan). It should not be treated as long-lived production hosting.

### What I learned / next steps

This assignment exercises **file-format interoperability, coordinate reference system handling, geometric validation, REST contract design, failure semantics, persistent evidence, deterministic spatial analysis and reviewer-first UI design**.

Possible follow-ups—**not claimed as implemented**—include authentication and user-scoped files, retention/deletion controls, background processing for large surveys, async job status, certified geodesic/field benchmarking, database backups and a separate standalone GeoInsight repository after the assessment.

---

## Repository scope and project separation

**This README is exclusively about the Aereo GeoInsight assessment.** This Git repository was originally created for a separate **Spatial Asset Management Platform** with asset CRUD, JWT/RBAC, PostGIS queries, audit logs and location history. Its original documentation has been preserved intact at **[docs/SPATIAL_ASSET_MANAGEMENT_PLATFORM.md](docs/SPATIAL_ASSET_MANAGEMENT_PLATFORM.md)**.

The original platform's APIs are **not** part of the public GeoInsight deployment, and its unfinished frontend is **not** presented as a completed feature here. Splitting the two applications into independent repositories is future cleanup, not a requirement for this submission.

**V2 release documentation:** [Changelog](CHANGELOG.md) · [Release notes (draft)](docs/GEOINSIGHT_V2_RELEASE_NOTES.md) · [Architecture](docs/GEOINSIGHT_V2_ARCHITECTURE.md) · [Verification evidence](docs/GEOINSIGHT_V2_VERIFICATION.md) · [MIT License](LICENSE)

**Further technical context:** [GeoInsight supporting guide](docs/GEOINSIGHT_TECHNICAL_GUIDE.md) · [API implementation](aereo/api.py) · [GIS engine](app/services/geospatial/engine.py) · [Regression tests](aereo_tests/) · [CI workflow](.github/workflows/aereo-ci.yml)

---

<div align="center">

### Explore the working application

**[Open GeoInsight →](https://geoinsight-aereo.onrender.com/geospatial)** · **[Try Swagger →](https://geoinsight-aereo.onrender.com/docs)** · **[Follow the reviewer guide →](https://geoinsight-aereo.onrender.com/geospatial/guide)**

<sub>GeoInsight · Aereo Geospatial File Measurement API assessment · October 2026</sub>

</div>

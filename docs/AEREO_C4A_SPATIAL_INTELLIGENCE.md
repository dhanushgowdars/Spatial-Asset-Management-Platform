# C4A — Deterministic 2D Spatial Intelligence

**Base commit:** `de0e1a6` on `feature/aereo-geospatial-measurements`.
**Status:** Prepared for user-side verification; **not yet committed or deployed**.

C4A adds three **optional** standalone assessment APIs. The original three
mandatory KML/Shapefile upload + retrieval routes remain unchanged. All new
analyses consume IDs of datasets *already uploaded and persisted* through
`POST /api/files/`, and use their validated EPSG:4326 display geometry.

## Routes and request bodies

```http
POST /api/analysis/compare
Content-Type: application/json

{"baseline_file_id":"<32-character-file-id>","current_file_id":"<32-character-file-id>"}
```

Returns `metrics` with baseline/current footprint area, added and removed area,
unchanged overlap, union, net change (all m²), percentage overlap for each
survey, and intersection-over-union percentage. `change_geojson` contains the
WGS84 added/removed/overlap shapes, suitable for map display.

```http
POST /api/analysis/topology
Content-Type: application/json

{"file_id":"<32-character-file-id>","reference_file_id":"<optional-site-boundary-id>"}
```

Reports polygon **area** overlaps (nonzero shared interior, not edge touches),
affected feature IDs and areas. When a known reference site boundary is supplied,
computes *uncovered within reference* and *outside reference* areas and GeoJSON.
Without a reference: `gaps_evaluated=false`, and **no speculative gap claims**.

```http
POST /api/analysis/route-zones
Content-Type: application/json

{"route_file_id":"<line-dataset-id>","zone_file_id":"<polygon-dataset-id>"}
```

Returns each measured line's length inside each zone and outside all zones,
plus a union-of-zones inside length that does **not double count** overlapping
zones. `intersection_geojson` contains WGS84 clipped route segments.
Touching a polygon at a single point has zero intersecting *length* and is not
reported as a positive-length route crossing.

## Correctness guarantees and limits

- **One common UTM projected metre CRS** is selected per complete analysis.
  Original inputs may have differing CRSs; all uploaded geometry has already
  been transformed to EPSG:4326 by the existing engine. Planar Shapely overlay
  operations run only *after* common-metric reprojection. Calculations never
  multiply degree coordinates as if they were metres.
- Reject cross-dateline, polar, wide/global or overly large studies: maximum
  5 degrees along each WGS84 axis and 250 km projected bounding diagonal.
  A warning is included for larger permitted local extents. Not intended for
  cadastral-grade or global-extent surveying.
- Maximum **250** stored features and **30,000** coordinates per input dataset
  for analysis; topology maximum **120** polygons; route-zone maximum **120**
  lines and **120** polygons. Maximum **150** detailed output features.
  Capped detail output exposes issue counts and truncation rather than implying
  there were only 150 overlaps.
- Polygon footprints within each survey are unioned before comparison:
  overlapping component polygons are **not double counted** in area changes.
- Invalid or unmeasured geometries are excluded with an explicit
  `partial=true`, `excluded_features` and warning. Point-only datasets are
  rejected with 422 for polygon/route requirements. The user must inspect
  incomplete analyses; they are not automatically certified as complete.
- Stored results remain unchanged by these read-only calculations. Unknown IDs
  return 404; unsupported study extents/geometry combinations return 422.
- Inputs are **2D vectors only**. No height, terrain DEM, stockpile volume,
  raster orthomosaic or AI-derived measurement is claimed.
- Source audit values, source files and reports belong to the existing upload
  endpoints; these APIs produce derived read-only analysis, not new uploads.

## Demo fixtures (synthetic, independent of Aereo customer records)

- `aereo_samples/c4a_baseline.geojson`: one 100 m × 100 m UTM43N square.
- `aereo_samples/c4a_current.geojson`: the same square shifted 50 m east.
- `aereo_samples/c4a_topology.geojson`: two overlapping polygons.
- `aereo_samples/c4a_route.geojson`: one 140 m line.
- `aereo_samples/c4a_zone.geojson`: one 40 m-wide zone along the route.

After uploading the baseline/current files, the expected comparison output is
approximately **5,000 m² added, 5,000 m² removed, 5,000 m² overlap, 0 m² net**.
The topology fixture has a **5,000 m²** overlap between its two features. The
route passes **40 m** inside the demo zone. These are synthetic correctness
fixtures, *not* evidence of accuracy on Aereo real-world drone datasets.

## Verification before the C4A push

From project root on the Aereo feature branch:

```powershell
python -m pytest aereo_tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Expect **77** backend tests (previous 55 + 22 new) with the same upstream
production test present. Then rebuild `aereo/Dockerfile`, POST the sample files,
call the three new endpoints, and verify existing `/geospatial`, `/health`,
KML/Zipped-Shapefile uploads, quality, measurement and export routes still work.
Do not commit unrelated `AEREO_START_HERE.md` or `AEREO_FRONTEND_README.md`.
Do not claim an end-to-end browser *comparison view* yet: that is the next
frontend integration milestone.

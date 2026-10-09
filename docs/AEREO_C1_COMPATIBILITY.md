# C1 — Independent compatibility and real-data verification

**Scope:** Improve resilience of the existing required KML and zipped Shapefile API without introducing new formats, extra calculations, or a breaking response schema. **Keep the P0 API stable.**

## What the new tests demonstrate

- ZIP with uppercase `.SHP/.SHX/.DBF/.PRJ` and a nested folder parses normally.
- Shapefile DBF attributes encoded in CP1252 are decoded using `.cpg`, preserving `Café`.
- Source projection with US survey feet (EPSG:2272) is transformed before reporting a 100-ft test line in metric units (about 30.48 m). **Conversion tests use controlled geometries, not survey-certified measurement precision.**
- KML Placemarks in nested folders are discovered.
- Invalid WGS84 longitudes from a Shapefile are **rejected per feature** rather than displayed as valid points.
- Max-feature guard rejects 5,001 features before per-feature processing.
- Case-insensitive duplicate ZIP paths are rejected.

Run from repository root: `python -m pytest aereo_tests -q`.

## External real-world input QA — REQUIRED BEFORE C1 SIGNOFF

Our bundled and scripted fixtures are synthetic. They do not prove third-party GIS compatibility. Obtain *at least one* genuine third-party source file, e.g. Natural Earth's **1:110m rivers and lake centerlines** ZIP download at:

https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-rivers-lake-centerlines/

Also consider a geographic country/polygon layer or the QGIS Alaska samples at:

https://github.com/opengisch/QGIS-Sampledata

**How to test:** Download the original zipped Shapefile (not the outer QA pack). Do not extract and recompress it unless the actual supplied archive has multiple Shapefiles. Upload through Browse Files and the FastAPI `/api/files/` route; verify feature count, attributes, geometry, statuses, error messages, and GeoJSON map rendering. Record filename, source URL, license, source CRS, SHA-256 digest and screenshots. Compare representative measurements in QGIS or via an independent geodesic reference when appropriate.

**Important limitation:** Natural Earth 110m data is small-scale, generalized geographic data covering large areas. It tests ingestion and map-display resilience, **not survey-grade area/length accuracy**. The current CRS engine's local projected calculations can be distorted over large or dateline-crossing features. Never advertise world-scale projected lengths as ground-truth. Fix or explicitly flag geospatial accuracy limitations before claiming those outputs as accurate.

## C1 phase completion gate

- [ ] `python -m pytest aereo_tests -q` passes **25 or more** tests on developer machine.
- [ ] Existing frontend `npm --prefix frontend run lint` and `npm --prefix frontend run build` pass.
- [ ] Actual independent external Shapefile ingestion exercised; any mismatch captured as a bug and corrected or documented.
- [ ] `git diff --check` clean and no credentials/databases or build artifacts staged.
- [ ] Only intended C1 paths committed and pushed to `feature/aereo-geospatial-measurements`.
- [ ] `docs/AEREO_PHASE_TRACKER.md` updated with SHA, results, and sources used.

**Next phase:** C2 Survey QA and GeoJSON/KMZ readers — but pause optional formats if Docker/cloud release is falling behind.

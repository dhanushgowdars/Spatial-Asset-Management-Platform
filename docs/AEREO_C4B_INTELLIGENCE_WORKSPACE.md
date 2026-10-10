# GeoInsight C4B — Reviewer Intelligence Workspace

Baseline: `18bb21b` feature branch (C4A tests and live comparison/topology/routes verified; CI green).

## What changed

- Independent review route at `/geospatial/intelligence` linked at the top of the existing `/geospatial` page. The original API and upload workflow are preserved.
- Tab 1: Survey QA and full measurement evidence from `/quality/`, `/summary/` and `/measurements/`, with download links to **server-generated** CSV and GeoJSON exports.
- Tab 2: Survey comparison with uploaded/saved baseline and current datasets, added/removed/overlap metrics, color-coded GeoJSON overlay and report export.
- Tab 3: Polygon topology: pair overlaps, optional reference-boundary comparison and issue geometry.
- Tab 4: Route–zone intersection: 2D clipped segments, inside/outside length and zone counts.
- Five synthetic sample GeoJSON files copied to the **frontend public samples** folder (required for Docker's built-in sample button).
- FastAPI production SPA route now supports `/geospatial/intelligence` when a reviewer refreshes the deep link.

## Scope limitations

Deterministic 2D vector overlays only; no drone photogrammetry, DEM/point-cloud processing, true 3D digital twins, cadastral accuracy guarantee or LLM inference. Analysis uses the C4A bounded local UTM study area constraints. Basemap is geometry-only by default with optional OpenStreetMap streets, no premium imagery access or API keys. All metrics come from backend outputs, not browser geometry calculations. The browser shows recent local entries; it does not provide an authenticated multiuser file catalogue.

## User-side acceptance gate

From project root:

```powershell
python -m pytest aereo_tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Expect **78 tests**, including new production deep-link coverage. Docker smoke-test:

```powershell
docker stop geoinsight-preview
docker build -f aereo/Dockerfile -t geoinsight:release .
docker run -d --rm --name geoinsight-preview -p 18140:8000 -v geoinsight-results:/data geoinsight:release
curl.exe -i http://localhost:18140/geospatial/intelligence
```

Expect HTML 200 on direct deep-link refresh. Open `http://localhost:18140/geospatial`, click **Open Spatial Intelligence**, then load verified examples for each tab. Compare: 5000 m² added/removed/overlap. Topology: one overlap pair 5000 m². Routes: one intersecting route and 40 m inside the zone. Verify QA issue details using `quality_demo.geojson` upload and authoritative CSV/GeoJSON links.

Do **not** commit if lint/build or checks fail. Don't stage unrelated root README drafts. No changes to legacy asset services or existing volume data.

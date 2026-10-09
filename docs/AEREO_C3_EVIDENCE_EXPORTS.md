# GeoInsight C3 — Measurement evidence and interoperable reporting

C3 extends C2 without changing the `measurement`, `geometry`, `crs`, `status` or
`measurement_crs` contract returned by the existing `/measurements/` API.
All existing source files and saved historical records remain readable. Old
records may not contain new `evidence` and `measurement_method` keys.

## Evidence fields (new, optional)

- Every safely transformed geometry: WGS84 bounding envelope
  `bbox_wgs84 = [min_lon, min_lat, max_lon, max_lat]` (degrees, **not metres**).
  A simple envelope is not an antimeridian-aware bbox.
- Polygon / MultiPolygon: `perimeter_m` including hole boundaries;
  `polygon_parts`; `centroid_wgs84` (lon,lat); method labels.
- LineString / MultiLineString: `line_parts`, total `segments`,
  `part_details` with projected part length and WGS84 start/end. The length
  represents geometry polyline length, **not** road-network route distance.
- Point / MultiPoint: `point_locations_wgs84` and `point_count`. No invented
  metric length or area; status remains `NOT_APPLICABLE`.
- Measured features: `measurement_method=projected_planar_geometry`; original
  per-feature measurement CRS and projection distortion warnings are retained.
- Invalid/untransformable features must not receive invented evidence.

Polygon centroids use planar geometry in the selected **measurement CRS**,
then transform back to WGS84. They may be outside concave polygons. Perimeter
and area are projected approximations; do not imply cadastral accuracy.

## Endpoints

- `GET /api/files/{id}/summary/`: status, feature counts, arithmetic sum of
  measured polygon areas (m²) and line lengths (m), warning count. These are
  **not** polygon unions: overlaps may be double-counted.
- `GET /api/files/{id}/export/?format=csv`: server-generated CSV with
  geometry and measurement information, source metadata, evidence and original
  properties encoded in a JSON column. Values sourced from user text are
  spreadsheet-formula escaped.
- `GET /api/files/{id}/export/?format=geojson`: WGS84 mapped features with
  measurement annotations and evidence; untransformable features lacking
  display geometry are omitted. Do not use GeoJSON feature count as a QA count.
- Existing `/geojson/` retains its original keys, adding optional evidence.
- Unknown ID: 404; invalid export format: 422.

## Smoke checks

Upload `.kml`, zipped Shapefile, `.geojson`, `.kmz`, retrieve measurement,
summary, CSV and GeoJSON exports. Check comparison against existing values,
CSV UTF-8 + quoting, and access again after restart.

Run `python -m pytest aereo_tests -q` and frontend lint/build prior to push.

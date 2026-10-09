# C2 — GeoJSON/KMZ Interoperability + Survey QA

**Implementation checkpoint:** feature code and tests prepared. **Not committed or deployed** until the Windows and GitHub checks pass.

## Why this matters to the reviewer

GeoInsight now returns machine-readable quality issues for each uploaded file rather than asking the reviewer to infer failures from the raw measurement list. This is a useful survey QA workflow, not an AI inference or an unsupported promise of survey-grade accuracy.

## Supported inputs and constraints

| Format | Parsing contract |
| --- | --- |
| `.kml` | KML Placemarks, supported geometries and source attributes |
| `.zip` | Exactly one Shapefile (`.shp/.shx/.dbf`), `.prj` required to measure safely |
| `.geojson` | RFC 7946 `FeatureCollection` or `Feature`, assumed WGS84 longitude/latitude; custom `crs` is rejected |
| `.kmz` | A safe ZIP containing **exactly one** `.kml` anywhere inside; all ZIP paths validated |

Limits from the existing engine still apply: 10 MiB uploaded bytes, 50 MiB expanded ZIP bytes, 40 ZIP entries, 5,000 features, 250,000 vertices per geometry. KMZ images/overlays are not parsed into measurements; no external resources are fetched.

Unsupported/malformed *individual* GeoJSON geometries become `FAILED` feature results while other features can succeed. Invalid JSON envelope, unsafe ZIP or duplicate KML paths are rejected with `422`. No fake measurements are generated for unknown CRS, Points or GeometryCollections.

## New endpoint

`GET /api/files/{file_id}/quality/`

Response shape:

```json
{
  "file_id": "...",
  "filename": "quality_demo.geojson",
  "status": "COMPLETED_WITH_ERRORS",
  "summary": {
    "total_features": 3,
    "measured": 1,
    "not_applicable": 1,
    "failed": 1,
    "unsupported": 0,
    "warning_features": 0,
    "error_features": 1,
    "issue_count": 1
  },
  "issues": [
    {
      "feature_id": "bad-location",
      "feature_index": 2,
      "geometry_type": "Point",
      "code": "TRANSFORM_FAILED",
      "severity": "ERROR",
      "message": "CRS/measurement error: Invalid longitude/latitude after CRS transformation"
    }
  ],
  "features": [{"id":"parcel-a","index":0,"geometry_type":"Polygon","status":"MEASURED","issue_codes":[]}]
}
```

The example `features` array above is shortened for readability. Actual output contains every feature and all issues.

Issue codes: `INVALID_GEOMETRY`, `EMPTY_GEOMETRY`, `CRS_MISSING`, `UNSUPPORTED_GEOMETRY`, `VERTEX_LIMIT_EXCEEDED`, `TRANSFORM_FAILED`, `PARSE_FAILED`, `FEATURE_PROCESSING_FAILED`, `PROJECTION_DISTORTION_WARNING`, `MEASUREMENT_WARNING`. Codes are derived deterministically from the engine's status/error/warning fields; past stored records are supported by computing the same report on retrieval.

**Status semantics:** `NOT_APPLICABLE` is not a failure for Points. `UNSUPPORTED` is distinguishable from `FAILED`. Large-extent projection warnings are not proof of an erroneous calculation, but warn that distortion matters.

## Manual review steps (no cloud needed)

1. Install requirements only if not already present, then `python -m pytest aereo_tests -q`.
2. Start `python -m uvicorn aereo.api:app --host 127.0.0.1 --port 18130` or rebuild `geoinsight:release` Docker image.
3. Open `/docs`, POST `aereo_samples/quality_demo.geojson`, copy the returned `id` and GET `/api/files/{id}/quality/`.
4. Check `summary.total_features=3`, `failed=1`, `measured=1`, `not_applicable=1`; preview valid features on the map.
5. Upload `aereo_samples/quality_demo.kmz` and check it succeeds with one Point and one Polygon.
6. Re-test mandatory KML and zipped Shapefile uploads and the 100m square. Restart service and verify both new and old records are retrievable.
7. If the current React frontend only displays original formats in its text, rebuild after applying the small C2 input-accept update. Full visual QA dashboard comes in C4.

## Remaining work / nonclaims

- C3: perimeter, centroid, WGS84 bbox, summary and export API extensions, measurement method metadata.
- C4: React QA severity panel, quality table, issue-based filtering and report download.
- Deployment and upload rate limiting not done by this patch.
- No certification of accuracy for all projections or global/polar datasets; independent geodesic comparison on Natural Earth had a maximum observed difference of 0.208% on that specific simplified river dataset.

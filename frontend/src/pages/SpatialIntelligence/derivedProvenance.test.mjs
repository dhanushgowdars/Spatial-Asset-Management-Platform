import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceDetail, withDerivedProvenance } from './presentation.mjs';

const analysis = {
  measurement_crs: 'EPSG:32643',
  method: 'projected_planar_polygon_overlay',
  baseline_file_id: 'baseline-id',
  current_file_id: 'current-id',
};

test('calculated overlay inherits actual CRS and reports correct operation', () => {
  const layer = withDerivedProvenance({ _category: 'added', geometry: { type: 'Polygon' }, properties: { area_m2: 5000 } }, analysis, 'compare');
  assert.equal(layer.properties._measurement_crs, 'EPSG:32643');
  assert.equal(layer.properties._status, 'CALCULATED');
  const detail = Object.fromEntries(sourceDetail(layer).summary);
  assert.equal(detail.Measurement, '5,000 m²');
  assert.equal(detail.Status, 'Calculated · derived overlay');
  assert.equal(detail['Calculation CRS'], 'EPSG:32643');
  assert.equal(detail.Method, 'projected planar polygon overlay');
  assert.match(detail['Spatial operation'], /current footprint minus baseline/i);
});

test('backend-provided provenance wins over fallback', () => {
  const layer = withDerivedProvenance({ _category: 'removed', properties: {
    area_m2: 25, _status: 'CALCULATED', _measurement_crs: 'EPSG:32644', _measurement_method: 'server_actual_method',
    _operation: 'server operation',
  }}, analysis, 'compare');
  assert.equal(layer.properties._measurement_crs, 'EPSG:32644');
  assert.equal(layer.properties._measurement_method, 'server_actual_method');
  assert.equal(layer.properties._operation, 'server operation');
});

test('route intersection does not mislabel length as area', () => {
  const layer = withDerivedProvenance({ _category: 'route_zone_intersection',geometry:{type:'LineString'},properties: { length_m: 40 } },
    { measurement_crs:'EPSG:32643', method:'projected_planar_line_polygon_overlay',route_file_id:'route',zone_file_id:'zone' }, 'routes');
  const detail = Object.fromEntries(sourceDetail(layer).summary);
  assert.equal(detail.Measurement, '40 m');
  assert.equal(detail.Status, 'Calculated · derived overlay');
  assert.match(detail['Spatial operation'], /route intersection/i);
});

test('uploaded source and unmeasured points remain unchanged', () => {
  const point = { _category: 'survey_point', geometry: {type:'Point'}, properties:{name:'Control point'} };
  assert.equal(withDerivedProvenance(point,analysis,'quality'),point);
  const source = Object.fromEntries(sourceDetail(point).summary);
  assert.equal(source.Measurement,'Not provided');
});

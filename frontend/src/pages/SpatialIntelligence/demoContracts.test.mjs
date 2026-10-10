import test from 'node:test';
import assert from 'node:assert/strict';
import { DEMOS, verifyDemo } from './demoContracts.mjs';
test('fixture names and roles are unambiguous', () => {
  assert.deepEqual(DEMOS.compare.files.map(f => f.name), ['c4a_baseline.geojson', 'c4a_current.geojson']);
  assert.deepEqual(DEMOS.routes.files.map(f => f.name), ['c4a_route.geojson', 'c4a_zone.geojson']);
});
test('survey comparison checks every metric with tolerance', () => {
  const d = { metrics: { baseline_area_m2: 10000, current_area_m2: 10000, added_area_m2: 5000, removed_area_m2: 5000, overlap_area_m2: 5000, intersection_over_union_pct: 33.3333 }};
  assert.equal(verifyDemo('compare', d).ok, true);
  d.metrics.removed_area_m2 = 0;
  assert.equal(verifyDemo('compare', d).ok, false);
});
test('QA cannot pass without the expected issue code', () => {
  const d = { quality: { summary: { total_features: 3, measured: 1, not_applicable: 1, failed: 1 }, issues: [] } };
  assert.equal(verifyDemo('quality', d).ok, false);
  d.quality.issues.push({ code: 'TRANSFORM_FAILED' });
  assert.equal(verifyDemo('quality', d).ok, true);
});
test('topology validates pair count and area', () => {
  assert.equal(verifyDemo('topology', { overlap_pair_count: 1, overlap_issues: [{ overlap_area_m2: 5000 }]}).ok, true);
});
test('routes validate all metrics, including outside distance', () => {
  const d = { summary: { route_count: 1, zone_count: 1, total_length_inside_any_zone_m: 40 }, routes: [{length_m: 140, outside_all_zones_m: 100}]};
  assert.equal(verifyDemo('routes', d).ok, true);
  d.routes[0].outside_all_zones_m = 0;
  assert.equal(verifyDemo('routes', d).ok, false);
});

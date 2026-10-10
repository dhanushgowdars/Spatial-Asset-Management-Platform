/* Deterministic fixture contracts. Never substitute expected values for API results. */
export const DEMOS = Object.freeze({
  quality: { files: [{ role: 'survey', name: 'quality_demo.geojson' }], expected: { total: 3, measured: 1, notApplicable: 1, failed: 1, code: 'TRANSFORM_FAILED' } },
  compare: { files: [{ role: 'baseline', name: 'c4a_baseline.geojson' }, { role: 'current', name: 'c4a_current.geojson' }], expected: { baseline: 10000, current: 10000, added: 5000, removed: 5000, overlap: 5000, iou: 33.3333 } },
  topology: { files: [{ role: 'survey', name: 'c4a_topology.geojson' }], expected: { pairs: 1, overlap: 5000 } },
  routes: { files: [{ role: 'route', name: 'c4a_route.geojson' }, { role: 'zone', name: 'c4a_zone.geojson' }], expected: { routes: 1, zones: 1, total: 140, inside: 40, outside: 100 } },
});

export function verifyDemo(mode, data) {
  if (!DEMOS[mode] || !data) return { ok: false, checks: [], message: 'Missing test result' };
  const e = DEMOS[mode].expected;
  const close = (actual, expected) => typeof actual === 'number' && Number.isFinite(actual) && Math.abs(actual - expected) <= Math.max(0.1, expected * 0.0001);
  let checks;
  if (mode === 'quality') {
    const s = data.quality?.summary || {};
    checks = [
      ['Feature count', s.total_features, e.total], ['Measured', s.measured, e.measured],
      ['Not applicable', s.not_applicable, e.notApplicable], ['Failed', s.failed, e.failed],
      ['Issue code', data.quality?.issues?.some(i => i.code === e.code) ? e.code : 'Not found', e.code],
    ];
  } else if (mode === 'compare') {
    const m = data.metrics || {};
    checks = [['Baseline area (m²)', m.baseline_area_m2, e.baseline], ['Current area (m²)', m.current_area_m2, e.current],
      ['Added area (m²)', m.added_area_m2, e.added], ['Removed area (m²)', m.removed_area_m2, e.removed],
      ['Overlap area (m²)', m.overlap_area_m2, e.overlap], ['IoU (%)', m.intersection_over_union_pct, e.iou]];
  } else if (mode === 'topology') {
    checks = [['Overlapping pairs', data.overlap_pair_count, e.pairs],
      ['First overlap area (m²)', data.overlap_issues?.[0]?.overlap_area_m2, e.overlap]];
  } else {
    checks = [['Routes', data.summary?.route_count, e.routes], ['Zones', data.summary?.zone_count, e.zones],
      ['Total route length (m)', data.routes?.[0]?.length_m, e.total],
      ['Inside zones (m)', data.summary?.total_length_inside_any_zone_m, e.inside],
      ['Outside zones (m)', data.routes?.[0]?.outside_all_zones_m, e.outside]];
  }
  const rendered = checks.map(([label, actual, expected]) => ({ label, actual, expected, pass: typeof expected === 'number' ? close(actual, expected) : actual === expected }));
  return { ok: rendered.every(x => x.pass), checks: rendered, message: rendered.every(x => x.pass) ? 'Live API output matches every independent fixture expectation.' : 'One or more values do not match the fixture contract. Inspect the output before relying on this analysis.' };
}

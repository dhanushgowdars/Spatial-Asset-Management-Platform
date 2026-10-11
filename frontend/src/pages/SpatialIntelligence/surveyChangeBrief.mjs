/** Explain existing deterministic survey-comparison results; do not rerun GIS calculations. */
export const CHANGE_BRIEF_SCHEMA = 'geoinsight_survey_change_brief';
const ID = /^[a-f0-9]{32}$/i;
const KEYS = [
  'baseline_area_m2', 'current_area_m2', 'added_area_m2', 'removed_area_m2',
  'overlap_area_m2', 'union_area_m2', 'net_change_m2', 'intersection_over_union_pct',
];
const nonnegative = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const absolute = value => typeof value === 'number' && Number.isFinite(value);
const cleanLabel = (value, fallback) => typeof value === 'string' && value.trim()
  ? value.slice(0, 160) : fallback;
const safeNotes = values => Array.isArray(values)
  ? values.filter(value => typeof value === 'string').slice(0, 12).map(value => value.slice(0, 320)) : [];
const near = (a, b, magnitude) => Math.abs(a - b) <= Math.max(0.001, magnitude * 1e-9);

/** Returns { ok, brief } or { ok:false, error } for an untrusted API result. */
export function buildSurveyChangeBrief(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return { ok: false, error: 'No comparison result is available.' };
  if (!ID.test(result.baseline_file_id || '') || !ID.test(result.current_file_id || '')) {
    return { ok: false, error: 'The comparison is missing valid dataset identifiers.' };
  }
  if (result.method !== 'projected_planar_polygon_overlay' || typeof result.measurement_crs !== 'string' || !result.measurement_crs.trim() || result.measurement_crs.length > 200) {
    return { ok: false, error: 'The projected comparison method or measurement CRS is unavailable.' };
  }
  const m = result.metrics;
  if (!m || typeof m !== 'object' || !KEYS.every(key => absolute(m[key]))) return { ok: false, error: 'Required comparison metrics are missing or nonfinite.' };
  const [baseline, current, added, removed, overlap, union, net, iou] = KEYS.map(key => m[key]);
  if (![baseline, current, added, removed, overlap, union].every(nonnegative) || union <= 0 || baseline <= 0 || current <= 0 || iou < 0 || iou > 100) {
    return { ok: false, error: 'Comparison metrics are outside supported numeric bounds.' };
  }
  const scale = Math.max(1, baseline, current, added, removed, overlap, union);
  if (!near(baseline, removed + overlap, scale) || !near(current, added + overlap, scale) ||
      !near(union, added + removed + overlap, scale) || !near(net, current - baseline, scale) ||
      Math.abs(iou - (overlap / union) * 100) > 0.001) {
    return { ok: false, error: 'Comparison totals are inconsistent; inspect the original API response.' };
  }

  const hasAdded = added > 0.0001;
  const hasRemoved = removed > 0.0001;
  let category, headline, explanation;
  if (!hasAdded && !hasRemoved) {
    category = 'unchanged';
    headline = 'No measurable footprint change';
    explanation = 'The supplied survey footprints overlap completely within the calculation precision.';
  } else if (hasAdded && hasRemoved && Math.abs(net) <= Math.max(0.001, scale * 1e-9)) {
    category = 'redistributed';
    headline = 'Equal overall area, different footprint';
    explanation = 'Added and removed regions offset in total area, but the mapped boundaries have changed. A zero net change does not mean the surveys are identical.';
  } else if (hasAdded && !hasRemoved) {
    category = 'expanded';
    headline = 'Measured footprint expanded';
    explanation = 'The current survey includes additional area without a measurable removed region.';
  } else if (!hasAdded && hasRemoved) {
    category = 'contracted';
    headline = 'Measured footprint contracted';
    explanation = 'The current survey excludes area present in the baseline footprint.';
  } else {
    category = 'mixed';
    headline = net > 0 ? 'Mixed footprint changes; net increase' : 'Mixed footprint changes; net decrease';
    explanation = 'Both added and removed regions exist. Net area alone does not describe the full spatial change.';
  }

  const partial = result.partial === true;
  const exclude = result.excluded_features && typeof result.excluded_features === 'object' ? result.excluded_features : {};
  const excludedCount = ['baseline', 'current'].reduce((total, key) => total + (Array.isArray(exclude[key]) ? exclude[key].length : 0), 0);
  const warnings = safeNotes(result.warnings);
  const brief = {
    report_type: CHANGE_BRIEF_SCHEMA,
    schema_version: '1.0',
    source: 'existing_api_comparison_result',
    datasets: {
      baseline: { id: result.baseline_file_id.toLowerCase(), filename: cleanLabel(result.baseline_filename, 'Baseline dataset') },
      current: { id: result.current_file_id.toLowerCase(), filename: cleanLabel(result.current_filename, 'Current dataset') },
    },
    interpretation: { category, headline, explanation,
      review_note: 'Inspect added (green), removed (red), and unchanged (blue) regions against the original input surveys before taking operational decisions.' },
    metrics: Object.fromEntries(KEYS.map(key => [key, m[key]])),
    derived_display: {
      net_change_pct_of_baseline: Number((100 * net / baseline).toFixed(4)),
      added_pct_of_union: Number((100 * added / union).toFixed(4)),
      removed_pct_of_union: Number((100 * removed / union).toFixed(4)),
      overlap_pct_of_union: Number((100 * overlap / union).toFixed(4)),
    },
    calculation: { method: result.method, measurement_crs: result.measurement_crs, unit: 'm2', projection_basis: '2D projected planar polygon overlay' },
    quality: { partial, excluded_feature_count: excludedCount, warnings },
    limitations: [
      'Deterministic presentation of API-computed 2D polygon overlays; not an independent area recalculation.',
      'Net area change may be zero even when additions and removals occur in different locations.',
      'Excluded or invalid source features can make an analysis partial; review the original data.',
      'Differences describe supplied polygon footprints, not proof of physical construction, field-survey accuracy, or legal boundary changes.',
    ],
  };
  return { ok: true, brief };
}

export function changeBriefDownloadName(brief) {
  if (!brief || brief.report_type !== CHANGE_BRIEF_SCHEMA || !ID.test(brief.datasets?.baseline?.id || '') || !ID.test(brief.datasets?.current?.id || '')) throw new Error('Cannot download an unverified brief');
  return `geoinsight-survey-change-${brief.datasets.baseline.id.slice(0, 8)}-to-${brief.datasets.current.id.slice(0, 8)}.json`;
}

export function briefNumber(value, maximumFractionDigits = 2) {
  if (!Number.isFinite(value)) return '—';
  const formatted = value.toLocaleString('en-IN', { maximumFractionDigits });
  return /^-0(?:\.0+)?$/.test(formatted) ? formatted.slice(1) : formatted;
}

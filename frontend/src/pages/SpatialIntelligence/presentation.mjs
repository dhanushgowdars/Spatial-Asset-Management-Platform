/** Presentation-only helpers. Spatial measurements remain authoritative in the API. */
export function asObject(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value;
  if (typeof value === 'string' && value.trim().startsWith('{')) {
    try { const parsed = JSON.parse(value); return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null; }
    catch { return null; }
  }
  return null;
}
export function numberText(value, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value)
    ? (Math.abs(value) < 1e-10 ? 0 : value).toLocaleString('en-IN', { maximumFractionDigits: digits })
    : '—';
}
function unitText(unit) { return unit === 'm2' ? 'm²' : unit === 'm' ? 'm' : unit || ''; }
export function measurementText(props) {
  if (!props) return null;
  const calculated = props.area_m2 != null ? { value: props.area_m2, unit: 'm2' }
    : props.length_m != null ? { value: props.length_m, unit: 'm' }
      : asObject(props._measurement ?? props.measurement);
  return calculated && typeof calculated.value === 'number'
    ? `${numberText(calculated.value)} ${unitText(calculated.unit)}`.trim() : null;
}
export function humanLabel(field) {
  const names = {
    _measurement_crs: 'Calculation CRS', measurement_crs: 'Calculation CRS', crs: 'Source CRS',
    _measurement_method: 'Calculation method', measurement_method: 'Calculation method',
    bbox_wgs84: 'WGS84 bounds', centroid_wgs84: 'Centroid (WGS84)',
    point_locations_wgs84: 'Point coordinates (WGS84)', perimeter_m: 'Perimeter',
    polygon_parts: 'Polygon parts', line_parts: 'Line parts',
    start_wgs84: 'Start position', end_wgs84: 'End position',
    segments: 'Segments', area_m2: 'Area', length_m: 'Length',
    route_feature_id: 'Route feature ID', zone_feature_id: 'Zone feature ID',
    survey_id: 'Survey feature ID', feature_id: 'Feature ID',
    bbox_order: 'Bounds order', id: 'Record ID'
  };
  return names[field] || field.replace(/^_/, '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function coordinateText(coords) {
  return `${numberText(coords[0], 6)}° E, ${numberText(coords[1], 6)}° N`;
}
export function displayValue(field, value) {
  if (value == null) return '—';
  if (typeof value === 'number') return `${numberText(value, field === 'perimeter_m' || /_m2?$/.test(field) ? 2 : 6)}${field.endsWith('_m2') ? ' m²' : field.endsWith('_m') ? ' m' : ''}`;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (field === 'bbox_wgs84' && Array.isArray(value) && value.length === 4)
    return `W ${numberText(value[0], 5)}°, S ${numberText(value[1], 5)}° · E ${numberText(value[2], 5)}°, N ${numberText(value[3], 5)}°`;
  if ((field === 'centroid_wgs84' || field === 'start_wgs84' || field === 'end_wgs84') && Array.isArray(value) && value.length >= 2) return coordinateText(value);
  if (field === 'point_locations_wgs84' && Array.isArray(value)) return `${value.length} mapped point${value.length === 1 ? '' : 's'}`;
  if (Array.isArray(value)) return value.length === 0 ? 'None' : `${value.length} item${value.length === 1 ? '' : 's'} (see downloaded JSON)`;
  const object = asObject(value);
  if (object) return `${Object.keys(object).length} metadata field${Object.keys(object).length === 1 ? '' : 's'} (see downloaded JSON)`;
  if (typeof value === 'string') return value.replaceAll('_', ' ');
  return String(value);
}
export function evidencePairs(raw) {
  const evidence = asObject(raw) || {};
  const lead = ['perimeter_m', 'centroid_wgs84', 'bbox_wgs84', 'point_count', 'polygon_parts', 'line_parts', 'segments', 'start_wgs84', 'end_wgs84'];
  const entries = Object.entries(evidence);
  return [...lead.filter(key => Object.hasOwn(evidence, key)).map(key => [humanLabel(key), displayValue(key, evidence[key])]),
    ...entries.filter(([key]) => !lead.includes(key)).map(([key, value]) => [humanLabel(key), displayValue(key, value)])];
}
export function sourceMeasurement(feature) {
  return measurementText(feature?.properties) || '—';
}
// GEOINSIGHT_DERIVED_PROVENANCE_V1: metadata for overlay output is inherited
// only from the authoritative server analysis result, never calculated in React.
const DERIVED_OPERATION_LABELS = {
  added: 'Current footprint minus baseline footprint',
  removed: 'Baseline footprint minus current footprint',
  unchanged_overlap: 'Intersection of baseline and current footprints',
  overlap_area: 'Intersection of two survey parcels',
  uncovered_within_reference: 'Reference boundary minus surveyed footprint',
  outside_reference: 'Surveyed footprint minus reference boundary',
  route_zone_intersection: 'Route intersection with selected zone',
};
export function withDerivedProvenance(feature, analysis, mode) {
  if (!feature || !analysis || mode === 'quality') return feature;
  const existing = feature.properties || {};
  const category = feature._category || existing.category || (mode === 'routes' ? 'route_zone_intersection' : 'overlap_area');
  const isCalculated = Number.isFinite(existing.area_m2) || Number.isFinite(existing.length_m);
  if (!isCalculated) return feature;
  const sourceIds = mode === 'compare'
    ? [analysis.baseline_file_id, analysis.current_file_id]
    : mode === 'topology' ? [analysis.file_id, analysis.reference_file_id]
      : [analysis.route_file_id, analysis.zone_file_id];
  return { ...feature, properties: {
    ...existing,
    _status: existing._status || 'CALCULATED',
    ...(existing._measurement_crs || !analysis.measurement_crs ? {} : { _measurement_crs: analysis.measurement_crs }),
    ...(existing._measurement_method || !analysis.method ? {} : { _measurement_method: analysis.method }),
    _operation: existing._operation || DERIVED_OPERATION_LABELS[category] || 'Projected spatial overlay',
    _source_file_ids: existing._source_file_ids || sourceIds.filter(Boolean),
  }};
}

export function sourceDetail(feature) {
  const p = feature?.properties || {};
  const measure = asObject(p._measurement ?? p.measurement);
  const evidence = p._evidence ?? p.evidence;
  const reserved = new Set(['_measurement','measurement','_evidence','evidence','_measurement_crs','measurement_crs','_measurement_method','measurement_method','_status','status','_error','error','area_m2','length_m','category','_operation','_source_file_ids']);
  const summary = [
    ['Geometry', feature?.geometry?.type || 'Unavailable'],
    ['Measurement', measurementText(p) || 'Not provided'],
    ['Status', p._status === 'CALCULATED' ? 'Calculated · derived overlay' : displayValue('status', p._status ?? p.status ?? (measure ? 'MEASURED' : 'Not provided'))],
    ['Calculation CRS', p._measurement_crs ?? p.measurement_crs ?? 'Not applicable'],
    ['Method', displayValue('method', p._measurement_method ?? p.measurement_method ?? 'Not provided')],
    ...(p._operation ? [['Spatial operation', p._operation]] : []),
  ];
  if (p._error ?? p.error) summary.push(['Issue', String(p._error ?? p.error)]);
  return { summary, evidence: evidencePairs(evidence), attributes: Object.entries(p)
    .filter(([key]) => !reserved.has(key)).map(([key, val]) => [humanLabel(key), displayValue(key,val)]) };
}
export function qualityDetail(item) {
  if (!item) return {summary:[],evidence:[]};
  const measurement = measurementText({measurement:item.measurement});
  const summary = [
    ['Geometry', item.geometry_type || 'Unavailable'], ['Status', item.status || 'Unknown'],
    ['Measurement', measurement || (item.status === 'FAILED' ? 'Not measured — validation failed' : 'Not applicable')],
    ['Source CRS', item.crs || 'Not provided'], ['Calculation CRS', item.measurement_crs || 'Not applicable'],
    ['Method', displayValue('method', item.measurement_method || 'Not applicable')],
  ];
  if (item.error) summary.push(['Issue', item.error]);
  return { summary, evidence: evidencePairs(item.evidence) };
}
export function qualityCrsNote(info, rows) {
  const source = info?.crs || 'Not provided';
  const projected = [...new Set((rows || []).filter(row => row.status === 'MEASURED' && row.measurement_crs).map(row => row.measurement_crs))];
  const calculated = !projected.length ? 'No successful measurements' : projected.length === 1 ? projected[0] : projected.join(', ');
  return `Source CRS: ${source} · Calculation CRS: ${calculated}`;
}

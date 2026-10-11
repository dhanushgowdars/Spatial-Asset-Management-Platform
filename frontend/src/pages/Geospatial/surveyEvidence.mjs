/** Lightweight presentation helpers for the persisted GeoInsight evidence. */
const FILE_ID = /^[a-f0-9]{32}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const MAX_REPORT_CHARS = 8 * 1024 * 1024;

export function reportUrl(id) {
  if (typeof id !== 'string' || !FILE_ID.test(id)) throw new Error('Invalid dataset ID.');
  return `/api/files/${id}/verification-report/`;
}

export function evidenceSummary(dataset) {
  const metadata = dataset?.metadata || {};
  const items = dataset?.measurements?.measurements;
  if (!Array.isArray(items)) return null;
  const measured = items.filter(item => item?.status === 'MEASURED');
  const failed = items.filter(item => item?.status === 'FAILED');
  const warnings = items.filter(item => Array.isArray(item?.warnings) && item.warnings.length > 0);
  const projections = [...new Set(measured.map(item => item.measurement_crs).filter(Boolean))];
  return {
    featureCount: Number.isInteger(metadata.feature_count) ? metadata.feature_count : items.length,
    measured: measured.length,
    failed: failed.length,
    remaining: items.length - measured.length - failed.length,
    warnings: warnings.length,
    projectionLabel: projections.length === 1 ? projections[0] : projections.length ? `${projections.length} measurement CRSs` : 'Not applicable',
    sha256: typeof metadata.sha256 === 'string' && SHA256.test(metadata.sha256) ? metadata.sha256 : null,
    sourceCRS: metadata.crs || 'Unknown',
  };
}

export function verifyReportIdentity(report, metadata) {
  if (!report || report.report_type !== 'geoinsight_measurement_verification' || report.schema_version !== '1.0') {
    throw new Error('Unexpected verification report format.');
  }
  if (!metadata || typeof metadata.id !== 'string' || !FILE_ID.test(metadata.id) ||
      typeof metadata.sha256 !== 'string' || !SHA256.test(metadata.sha256)) {
    throw new Error('Current dataset metadata is incomplete.');
  }
  if (report.provenance?.file_id !== metadata.id || report.provenance?.input_sha256 !== metadata.sha256 ||
      report.processing?.feature_count !== metadata.feature_count) {
    throw new Error('Report identity does not match the selected dataset.');
  }
  if (!Array.isArray(report.features) || report.features.length !== metadata.feature_count || !Array.isArray(report.limitations)) {
    throw new Error('Report content is incomplete.');
  }
  return true;
}

export async function retrieveVerificationReport(metadata, { signal, fetcher = fetch } = {}) {
  const response = await fetcher(reportUrl(metadata?.id), { signal, cache: 'no-store' });
  if (!response.ok) throw new Error(`Verification report unavailable (HTTP ${response.status}).`);
  const contentType = response.headers?.get?.('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) throw new Error('Expected JSON verification report.');
  const lengthHeader = Number(response.headers?.get?.('content-length') || 0);
  if (lengthHeader > MAX_REPORT_CHARS) throw new Error('Verification report is too large for browser download.');
  const text = await response.text();
  if (text.length > MAX_REPORT_CHARS) throw new Error('Verification report exceeds the browser download limit.');
  let report;
  try { report = JSON.parse(text); }
  catch { throw new Error('Verification report returned invalid JSON.'); }
  verifyReportIdentity(report, metadata);
  return text;
}

export function reportFilename(fileId) {
  reportUrl(fileId);
  return `geoinsight-verification-${fileId}.json`;
}

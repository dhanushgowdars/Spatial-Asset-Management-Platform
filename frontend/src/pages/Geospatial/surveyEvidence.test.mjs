import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evidenceSummary, reportUrl, reportFilename, verifyReportIdentity, retrieveVerificationReport } from './surveyEvidence.mjs';
const id = 'a'.repeat(32);
const hash = 'b'.repeat(64);
const meta = { id, sha256: hash, feature_count: 3, crs: 'EPSG:4326' };
const data = { metadata: meta, measurements: { measurements: [
  { status: 'MEASURED', measurement_crs: 'EPSG:32643', warnings: [] },
  { status: 'FAILED', warnings: [{ code: 'test' }] },
  { status: 'NOT_APPLICABLE' },
] } };
const report = { report_type: 'geoinsight_measurement_verification', schema_version: '1.0', provenance: {file_id:id,input_sha256:hash}, processing:{feature_count:3}, features:[{},{},{}], limitations:['Not certified'] };
test('valid file ID yields only same-origin report URL and safe fixed filename', () => {
  assert.equal(reportUrl(id), `/api/files/${id}/verification-report/`);
  assert.equal(reportFilename(id), `geoinsight-verification-${id}.json`);
  for (const invalid of ['', '../health', 'a'.repeat(31), 'a'.repeat(32) + '?evil=1', '%2e%2e', 'A'.repeat(32)]) {
    assert.throws(() => reportUrl(invalid), /Invalid dataset ID/);
  }
});
test('evidence summary counts are based on real returned statuses; no invented metrics', () => {
  assert.deepEqual(evidenceSummary(data), { featureCount:3, measured:1, failed:1, remaining:1, warnings:1, projectionLabel:'EPSG:32643', sha256:hash, sourceCRS:'EPSG:4326' });
  assert.equal(evidenceSummary({}), null);
});
test('mixed measurement projections are explicitly disclosed', () => {
  const d = {metadata:meta, measurements:{measurements:[{status:'MEASURED',measurement_crs:'EPSG:32643'}, {status:'MEASURED',measurement_crs:'EPSG:32644'}]}};
  assert.equal(evidenceSummary(d).projectionLabel, '2 measurement CRSs');
});
test('report identity, fingerprint, feature count and schema are required', () => {
  assert.equal(verifyReportIdentity(report, meta), true);
  assert.throws(() => verifyReportIdentity({...report, provenance:{...report.provenance, input_sha256:'f'.repeat(64)}},meta),/does not match/);
  assert.throws(() => verifyReportIdentity({...report,features:[{}]},meta),/incomplete/);
  assert.throws(() => verifyReportIdentity({...report,schema_version:'invalid'},meta),/Unexpected/);
});
test('JSON is retrieved only on demand and mismatched identity aborts download', async () => {
  const expected = JSON.stringify(report);
  const fetcher = async (url,opts) => {
    assert.equal(url, reportUrl(id));
    assert.equal(opts.cache,'no-store');
    return {ok:true, headers:{get:k=>k==='content-type'?'application/json':null}, text:async()=>expected};
  };
  assert.equal(await retrieveVerificationReport(meta,{fetcher}), expected);
  await assert.rejects(() => retrieveVerificationReport(meta,{fetcher:async()=>({ok:true,headers:{get:()=> 'application/json'},text:async()=>JSON.stringify({...report,provenance:{...report.provenance,file_id:'c'.repeat(32)}})})}),/does not match/);
});
test('HTTP failure, incorrect content type, invalid JSON, oversized reports fail safely', async () => {
  await assert.rejects(() => retrieveVerificationReport(meta,{fetcher:async()=>({ok:false,status:404})}),/HTTP 404/);
  await assert.rejects(() => retrieveVerificationReport(meta,{fetcher:async()=>({ok:true,headers:{get:()=> 'text/html'}})}),/Expected JSON/);
  await assert.rejects(() => retrieveVerificationReport(meta,{fetcher:async()=>({ok:true,headers:{get:()=> 'application/json'},text:async()=>'{oops'})}),/invalid JSON/);
  await assert.rejects(() => retrieveVerificationReport(meta,{fetcher:async()=>({ok:true,headers:{get:k=>k==='content-type'?'application/json':'99999999'}})}),/too large/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { measurementText, sourceMeasurement, sourceDetail, qualityCrsNote, evidencePairs, qualityDetail, displayValue } from './presentation.mjs';

test('source measurements stored in underscore GeoJSON fields are shown directly', () => {
  const p = { _measurement: {type:'area',value:10000,unit:'m2'}, _measurement_crs:'EPSG:32643', _status:'MEASURED' };
  assert.equal(measurementText(p), '10,000 m²');
  assert.equal(sourceMeasurement({properties:p}), '10,000 m²');
  const detail = sourceDetail({properties:p,geometry:{type:'Polygon'}});
  assert.ok(detail.summary.some(x => x[0] === 'Calculation CRS' && x[1] === 'EPSG:32643'));
  assert.ok(detail.summary.some(x => x[0] === 'Measurement' && x[1] === '10,000 m²'));
});
test('routes source measurement and overlay length are shown', () => {
  assert.equal(sourceMeasurement({properties:{_measurement:{value:140,unit:'m'}}}), '140 m');
  assert.equal(sourceMeasurement({properties:{length_m:40}}), '40 m');
  assert.equal(sourceMeasurement({properties:{area_m2:0}}), '0 m²');
});
test('CRS description cannot mistake EPSG:4326 input for projected calculation CRS', () => {
  assert.equal(qualityCrsNote({crs:'EPSG:4326'},[{status:'MEASURED',measurement_crs:'EPSG:32643'},{status:'FAILED',measurement_crs:null}]), 'Source CRS: EPSG:4326 · Calculation CRS: EPSG:32643');
  assert.match(qualityCrsNote({crs:'EPSG:4326'},[]),/No successful measurements/);
});
test('evidence reads useful spatial measurements without printing JSON objects', () => {
  const p = evidencePairs({perimeter_m:439.01883,centroid_wgs84:[76.5005,12.0005],part_details:[{length_m:140}]});
  assert.deepEqual(p[0],['Perimeter','439.02 m']);
  assert.match(p[1][1],/76.5005° E/);
  assert.ok(!p.flat().join(' ').includes('{"'));
  assert.match(displayValue('bbox_wgs84',[75,12,76,13]),/W 75°/);
});
test('QA failed geometry keeps clear validation reason', () => {
  const d=qualityDetail({status:'FAILED',geometry_type:'Point',error:'Invalid longitude/latitude',crs:'EPSG:4326'});
  assert.deepEqual(d.summary.find(([k])=>k==='Measurement'),['Measurement','Not measured — validation failed']);
  assert.deepEqual(d.summary.find(([k])=>k==='Issue'),['Issue','Invalid longitude/latitude']);
});

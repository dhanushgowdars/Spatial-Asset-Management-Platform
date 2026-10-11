import assert from 'node:assert/strict';
import test from 'node:test';
import { buildSurveyChangeBrief, changeBriefDownloadName, briefNumber, CHANGE_BRIEF_SCHEMA } from './surveyChangeBrief.mjs';

const FIX = () => ({
  baseline_file_id: '1'.repeat(32), current_file_id: '2'.repeat(32),
  baseline_filename: 'baseline.geojson', current_filename: 'current.geojson',
  measurement_crs: 'EPSG:32643', method: 'projected_planar_polygon_overlay',
  partial: false, excluded_features: { baseline: [], current: [] }, warnings: ['Projected local UTM.'],
  metrics: { baseline_area_m2: 10000, current_area_m2: 10000, added_area_m2: 5000,
    removed_area_m2: 5000, overlap_area_m2: 5000, union_area_m2: 15000,
    net_change_m2: 0, intersection_over_union_pct: 33.3333 },
});

test('independent known-size fixture: equal area but 5,000 m² of added and removed is NOT unchanged', () => {
  const {ok, brief} = buildSurveyChangeBrief(FIX());
  assert.equal(ok, true);
  assert.equal(brief.interpretation.category, 'redistributed');
  assert.match(brief.interpretation.explanation, /zero net change/i);
  assert.equal(brief.metrics.added_area_m2, 5000);
  assert.equal(brief.metrics.removed_area_m2, 5000);
  assert.equal(brief.derived_display.added_pct_of_union, 33.3333);
  assert.equal(brief.report_type, CHANGE_BRIEF_SCHEMA);
});

test('unchanged polygon set produces unchanged, not expansion', () => {
  const v=FIX(); Object.assign(v.metrics,{added_area_m2:0,removed_area_m2:0,overlap_area_m2:10000,union_area_m2:10000,intersection_over_union_pct:100});
  assert.equal(buildSurveyChangeBrief(v).brief.interpretation.category,'unchanged');
});

test('only added region reports expansion', () => {
  const v=FIX();Object.assign(v.metrics,{current_area_m2:14000,added_area_m2:4000,removed_area_m2:0,overlap_area_m2:10000,union_area_m2:14000,net_change_m2:4000,intersection_over_union_pct:71.4286});
  const {brief,ok}=buildSurveyChangeBrief(v);assert.equal(ok,true);assert.equal(brief.interpretation.category,'expanded');assert.equal(brief.derived_display.net_change_pct_of_baseline,40);
});

test('only removed region reports contraction', () => {
  const v=FIX();Object.assign(v.metrics,{current_area_m2:7000,added_area_m2:0,removed_area_m2:3000,overlap_area_m2:7000,union_area_m2:10000,net_change_m2:-3000,intersection_over_union_pct:70});
  const {brief,ok}=buildSurveyChangeBrief(v);assert.equal(ok,true);assert.equal(brief.interpretation.category,'contracted');assert.equal(brief.metrics.net_change_m2,-3000);
});

test('mixed changes with net growth are distinguished from pure expansion',()=>{
  const v=FIX();Object.assign(v.metrics,{baseline_area_m2:10000,current_area_m2:11000,added_area_m2:3000,removed_area_m2:2000,overlap_area_m2:8000,union_area_m2:13000,net_change_m2:1000,intersection_over_union_pct:61.5385});
  const {brief,ok}=buildSurveyChangeBrief(v); assert.equal(ok,true);assert.equal(brief.interpretation.category,'mixed');
  assert.match(brief.interpretation.headline,/net increase/i);
});

test('mixed changes with net decrease are distinguished from pure contraction',()=>{
  const v=FIX();Object.assign(v.metrics,{baseline_area_m2:10000,current_area_m2:9000,added_area_m2:2000,removed_area_m2:3000,overlap_area_m2:7000,union_area_m2:12000,net_change_m2:-1000,intersection_over_union_pct:58.3333});
  const {brief,ok}=buildSurveyChangeBrief(v);assert.equal(ok,true);assert.match(brief.interpretation.headline,/net decrease/i);
});

test('partial source inputs and exclusion count remain visible',()=>{
  const v=FIX();v.partial=true;v.excluded_features.current=[{id:'broken'},{id:'invalid'}];v.warnings=['Some invalid source geometry excluded'];
  const {brief}=buildSurveyChangeBrief(v); assert.equal(brief.quality.partial,true);assert.equal(brief.quality.excluded_feature_count,2);assert.deepEqual(brief.quality.warnings,v.warnings);
});

test('mismatched area identities do not produce a convincing brief',()=>{
  const v=FIX(); v.metrics.added_area_m2=6500;
  assert.match(buildSurveyChangeBrief(v).error,/inconsistent/i);
});

test('inconsistent net and intersection-over-union metrics are rejected',()=>{
  const v=FIX();v.metrics.net_change_m2=500;assert.equal(buildSurveyChangeBrief(v).ok,false);
  const w=FIX();w.metrics.intersection_over_union_pct=80;assert.equal(buildSurveyChangeBrief(w).ok,false);
});

test('bad API identifiers, projection method, absent and NaN metrics all fail safely',()=>{
  const v=FIX();v.current_file_id='../etc/passwd';assert.equal(buildSurveyChangeBrief(v).ok,false);
  const w=FIX();w.method='geodesic_measurement';assert.equal(buildSurveyChangeBrief(w).ok,false);
  const q=FIX();delete q.metrics.union_area_m2;assert.equal(buildSurveyChangeBrief(q).ok,false);
  const n=FIX();n.metrics.net_change_m2=NaN;assert.equal(buildSurveyChangeBrief(n).ok,false);
});

test('zero or negative areas and zero union do not cause incorrect percentages',()=>{
  const v=FIX();v.metrics.baseline_area_m2=0;assert.equal(buildSurveyChangeBrief(v).ok,false);
  const w=FIX();w.metrics.union_area_m2=0;assert.equal(buildSurveyChangeBrief(w).ok,false);
  const n=FIX();n.metrics.removed_area_m2=-10;assert.equal(buildSurveyChangeBrief(n).ok,false);
});

test('on-demand downloadable JSON contains data and limitations, not fabricated map geometries',()=>{
  const {brief}=buildSurveyChangeBrief(FIX());
  assert.equal(brief.source,'existing_api_comparison_result');
  assert.equal(brief.calculation.method,'projected_planar_polygon_overlay');
  assert.equal(brief.calculation.measurement_crs,'EPSG:32643');
  assert.ok(brief.limitations.some(item=>/not.*independent/i.test(item)));
  assert.ok(!JSON.stringify(brief).includes('coordinates'));
  assert.equal(changeBriefDownloadName(brief),'geoinsight-survey-change-11111111-to-22222222.json');
  assert.throws(()=>changeBriefDownloadName({report_type: CHANGE_BRIEF_SCHEMA,datasets: {baseline:{id:'oops'},current:{id:'bad'}}}));
  assert.equal(briefNumber(Number.NaN),'—');
});

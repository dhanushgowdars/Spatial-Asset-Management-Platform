import test from 'node:test';
import assert from 'node:assert/strict';
import { paginateMeasurements, MEASUREMENT_PAGE_SIZE } from './measurementPagination.mjs';

const entries = count => Array.from({length: count}, (_, id) => ({ id }));

test('empty list has no phantom rows and reports zero results', () => {
  assert.deepEqual(paginateMeasurements([], 1), { rows: [], total: 0, page: 1, pageCount: 1, start: 0, end: 0 });
});
test('fewer than 50 features remain on one page', () => {
  const p = paginateMeasurements(entries(1), 1);
  assert.equal(p.pageCount, 1); assert.equal(p.start, 1); assert.equal(p.end, 1); assert.equal(p.rows[0].id, 0);
});
test('exactly 50 features do not create an extra page', () => {
  assert.equal(paginateMeasurements(entries(50), 2).pageCount, 1);
});
test('125 features are paged 50, 50, 25 with correct boundaries', () => {
  const a = entries(125);
  for(const [page, first, last, count] of [[1,0,49,50],[2,50,99,50],[3,100,124,25]]) {
    const p = paginateMeasurements(a, page);
    assert.equal(p.rows.length,count); assert.equal(p.rows[0].id,first); assert.equal(p.rows.at(-1).id,last);
    assert.equal(p.start, first + 1);assert.equal(p.end, last + 1);assert.equal(p.pageCount,3);
  }
});
test('negative and out-of-range page numbers clamp safely', () => {
  const a = entries(125);
  assert.equal(paginateMeasurements(a, -7).page,1);
  assert.equal(paginateMeasurements(a, 999).page,3);
  assert.equal(paginateMeasurements(a, NaN).page,1);
  assert.equal(paginateMeasurements(a, '2').page,1);
});
test('filters apply to the full source before page slicing', () => {
  const all=entries(120);
  const filtered=all.filter(x=>x.id%3===0);
  const p=paginateMeasurements(filtered, 1);
  assert.equal(p.total,40);assert.equal(p.pageCount,1);assert.equal(p.rows.at(-1).id,117);
});
test('out-of-range after a filter shrinks list is safe', () => {
  const p=paginateMeasurements(entries(2), 30);
  assert.equal(p.page,1);assert.equal(p.rows.length,2);
});
test('source array order and membership are not mutated', () => {
  const a=entries(52),snapshot=JSON.stringify(a);
  const page=paginateMeasurements(a,2);
  assert.equal(JSON.stringify(a),snapshot);assert.notEqual(page.rows,a);assert.equal(page.rows[0].id,50);
});
test('oversized or invalid page sizes fall back to a bounded 50', () => {
  for(const size of [-1,0,1000,3.5,NaN]) assert.equal(paginateMeasurements(entries(110),1,size).rows.length,MEASUREMENT_PAGE_SIZE);
});
test('valid custom page size is supported without changing content', () => {
  const p=paginateMeasurements(entries(53),3,25);
  assert.equal(p.rows.length,3);assert.equal(p.rows[0].id,50);assert.equal(p.pageCount,3);
});

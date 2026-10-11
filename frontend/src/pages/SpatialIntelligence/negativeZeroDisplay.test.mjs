import test from 'node:test';
import assert from 'node:assert/strict';
import { briefNumber } from './surveyChangeBrief.mjs';

test('negative zero from rounded projected metrics displays as zero', () => {
  assert.equal(briefNumber(-0), '0');
  assert.equal(briefNumber(-0.001), '0');
  assert.equal(briefNumber(-0.01), '-0.01');
  assert.equal(briefNumber(0), '0');
});
test('meaningful signs and Indian grouping are retained', () => {
  assert.equal(briefNumber(-2500.5), '-2,500.5');
  assert.equal(briefNumber(2500.5), '2,500.5');
  assert.equal(briefNumber(Number.NaN), '—');
});

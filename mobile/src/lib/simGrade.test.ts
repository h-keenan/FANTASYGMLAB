// Run with: node --experimental-strip-types --test src/lib/simGrade.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SIM_GRADES,
  simAttributeText,
  simGradeAria,
  simGradeCompare,
  simGradeFill,
  simGradeIndex,
  simGradeLegend,
  simGradeOf,
  simGradeRangeText,
  simGradeSpoken,
  simGradeText,
  simGradeTone,
} from './simGrade.ts';

test('12 bands, best first, indexed A+ = 11 .. F = 0', () => {
  assert.equal(SIM_GRADES.length, 12);
  assert.equal(simGradeIndex('A+'), 11);
  assert.equal(simGradeIndex('F'), 0);
  assert.equal(simGradeIndex(null), -1);
  assert.equal(simGradeIndex('Z'), -1);
});
test('one five-tone ramp: green, cyan, gold, orange, red', () => {
  assert.deepEqual(['A+', 'A-', 'B', 'C+', 'D', 'F'].map(simGradeTone), ['success', 'success', 'accent', 'gold', 'warning', 'danger']);
});
test('a ? for a scouting estimate and a range for the legend', () => {
  assert.equal(simGradeText({ grade: 'B+' }), 'B+');
  assert.equal(simGradeText({ grade: 'B+', grade_uncertain: true }), 'B+?');
  assert.equal(simGradeText({ grade: null }), '—');
  assert.equal(simGradeRangeText({ grade: 'B+', grade_range: ['B-', 'A-'] }), 'B-/A-');
  assert.equal(simGradeRangeText({ grade: 'B+' }), null);
});
test('speaks grades without a hyphen or a plus sign', () => {
  assert.equal(simGradeSpoken('B-'), 'B minus');
  assert.equal(simGradeSpoken('A+'), 'A plus');
  assert.equal(simGradeAria({ grade: 'B+', grade_uncertain: true, grade_range: ['B', 'A-'] }), 'Grade B plus, strong starter. Scouts are unsure: B to A minus.');
  assert.equal(simGradeAria(null), 'No grade');
});
test('sorts best grade first, no grade last', () => {
  const rows = [{ grade: 'C' as const }, { grade: null }, { grade: 'A-' as const }, { grade: 'B' as const }];
  assert.deepEqual(rows.sort(simGradeCompare).map((r) => r.grade), ['A-', 'B', 'C', null]);
});
test('legend covers every band; fill is coarse and monotone', () => {
  assert.deepEqual(simGradeLegend().map((r) => r.grade), [...SIM_GRADES]);
  const fills = SIM_GRADES.map(simGradeFill);
  assert.deepEqual(fills, [...fills].sort((a, b) => b - a));
  assert.equal(simGradeFill(null), 0);
});
test('attribute text and the clean grade input', () => {
  assert.equal(simAttributeText({ key: 'k', label: 'L', grade: 'C+', uncertain: true }), 'C+?');
  assert.equal(simGradeOf({ grade: null }), null);
  assert.equal(simGradeOf({ grade: 'A' })?.grade, 'A');
});

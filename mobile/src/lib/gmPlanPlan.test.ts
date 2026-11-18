import assert from 'node:assert/strict';
import test from 'node:test';

import { buildPlanSteps, buildPlanWhy, ordinal, planFacts, planStatTiles } from './gmPlanPlan.ts';

const SNAP = [
  { key: 'power', value: '11 of 12' },
  { key: 'capital', value: '1 of 12' },
  { key: 'odds', value: '0%' },
  { key: 'record', value: '3 - 7' },
];

test('ordinals', () => {
  assert.deepEqual([1, 2, 3, 11, 12, 13, 21, 22].map(ordinal), ['1st', '2nd', '3rd', '11th', '12th', '13th', '21st', '22nd']);
});

test('four tiles split value and note', () => {
  assert.deepEqual(
    planStatTiles(SNAP).map((t) => [t.label, t.value, t.note]),
    [
      ['This season', '11th', 'of 12'],
      ['Draft capital', '1st', 'of 12'],
      ['Playoff odds', '0%', undefined],
      ['Record', '3-7', undefined],
    ],
  );
  assert.deepEqual(planStatTiles([]), []);
});

test('steps follow stance, capital, then signal areas', () => {
  const steps = buildPlanSteps({
    stance: 'rebuilding',
    tradeCount: 2,
    partners: ['The Hospital', 'Just Win'],
    topConfidence: 'High',
    capital: planFacts(SNAP).capital,
    areas: [
      { key: 'a', title: 'Roster Construction', framing: 'Thin at WR', count: 1, hasSignal: true },
      { key: 'b', title: 'Where You Stand', framing: '', count: 0, hasSignal: false },
    ],
  });
  assert.deepEqual(steps.map((s) => s.title), ['Sell aging vets for picks', 'Stack draft capital', 'Roster Construction']);
  assert.equal(steps[0].summary, '2 ideas: The Hospital and Just Win');
});

test('why line needs a stance', () => {
  const why = buildPlanWhy('rebuilding', planFacts(SNAP), 14);
  assert.equal(why?.headline, '0% playoff odds, 3-7: sell now, buy youth');
  assert.equal(buildPlanWhy('', planFacts(SNAP), null), null);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { findManagerRow, gradeToneSlug, headlineChips, tradeDateLabel } from './managerTendencies.ts';

test('headlineChips splits and drops not-enough-data lead-ins', () => {
  assert.deepEqual(headlineChips('Targets WRs. Sells picks.'), ['Targets WRs', 'Sells picks']);
  assert.deepEqual(headlineChips('Not enough trades yet (2 trades).'), []);
  assert.deepEqual(headlineChips('Not enough trades yet (2 trades). Sells picks.'), ['Sells picks']);
  assert.deepEqual(headlineChips(null), []);
});

test('findManagerRow matches roster id then team name', () => {
  const data = {
    ok: true,
    is_premium: true,
    upsell: null,
    managers: [{ roster_id: 3, team_name: 'Big Dogs', owner_handle: 'a', headline: 'x' }],
  };
  assert.equal(findManagerRow(data, '', 3)?.roster_id, 3);
  assert.equal(findManagerRow(data, ' big dogs ')?.roster_id, 3);
  assert.equal(findManagerRow(data, 'nope'), undefined);
});

test('tradeDateLabel formats date and week, degrades to week only, never invents', () => {
  assert.equal(tradeDateLabel('2026-10-04', 5), 'Oct 4, 2026 · Wk 5');
  assert.equal(tradeDateLabel('2026-10-04', 0), 'Oct 4, 2026');
  assert.equal(tradeDateLabel('', 7), 'Week 7');
  assert.equal(tradeDateLabel(null, null), '');
});

test('gradeToneSlug maps server tones to semantic colors', () => {
  assert.equal(gradeToneSlug('success'), 'success');
  assert.equal(gradeToneSlug('positive'), 'accent');
  assert.equal(gradeToneSlug('risk'), 'danger');
  assert.equal(gradeToneSlug('neutral'), 'muted');
  assert.equal(gradeToneSlug(undefined), 'muted');
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { findManagerRow, headlineChips } from './managerTendencies.ts';

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

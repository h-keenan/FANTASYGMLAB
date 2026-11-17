import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildRosterBasis } from './rosterBasis.ts';

type P = { id: string; position: string | null; slot: string | null; roster_slot?: 'starter' | 'bench' | 'ir' | 'taxi' };
const p = (id: string, position: string | null, slot: string | null, roster_slot?: P['roster_slot']): P => ({ id, position, slot, roster_slot });

test('best ball folds starters and active bench into one position-ordered roster with slots stripped', () => {
  const basis = buildRosterBasis<P>(
    [p('a', 'WR', 'WR1', 'starter'), p('b', 'QB', 'QB', 'starter')],
    [p('c', 'RB', null, 'bench'), p('d', 'TE', null, 'ir'), p('e', 'ZZ', null, 'taxi')],
    true,
  );
  assert.deepEqual(basis.activeBench.map((x) => x.id), ['b', 'c', 'a']);
  assert.ok(basis.activeBench.every((x) => x.slot === null));
  assert.deepEqual(basis.irBench.map((x) => x.id), ['d']);
  assert.deepEqual(basis.taxiBench.map((x) => x.id), ['e']);
});

test('a normal roster keeps starters as is and position-orders the bench', () => {
  const basis = buildRosterBasis<P>([p('a', 'WR', 'WR1', 'starter')], [p('x', 'TE', null, 'bench'), p('y', 'QB', null, 'bench')], false);
  assert.deepEqual(basis.starters.map((x) => x.id), ['a']);
  assert.deepEqual(basis.activeBench.map((x) => x.id), ['y', 'x']);
  assert.equal(basis.starters[0].slot, 'WR1');
});

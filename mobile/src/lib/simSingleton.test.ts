// Run with: node --experimental-strip-types --test src/lib/simSingleton.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simBlockable, simSingletonRuleOn, simSingletonMessage, simSingletonWarnings, simTradeSeedFor } from './simGame.ts';

const me = [{ id: 'mk', pos: 'K' }, { id: 'md', pos: 'DEF' }, { id: 'mw', pos: 'WR' }] as never[];
const them = [{ id: 'tk', pos: 'K' }, { id: 'td', pos: 'DEF' }, { id: 'tw', pos: 'WR' }] as never[];

test('they receive a second kicker: the message names the partner and the way out', () => {
  const w = simSingletonWarnings(me, them, ['mk'], ['pick:1']);
  assert.deepEqual(w, [{ team: 'them', pos: 'K' }]);
  const text = simSingletonMessage(w, 'The tickle monster');
  assert.match(text, /The tickle monster already has a kicker/);
  assert.match(text, /Ask for their kicker back/);
  assert.doesNotMatch(text, /^You/);
});

test('you receive a second kicker; both sides and a defense; a swap and unrelated trades warn about nothing', () => {
  const w = simSingletonWarnings(me, them, ['mw'], ['tk']);
  assert.deepEqual(w, [{ team: 'you', pos: 'K' }]);
  assert.match(simSingletonMessage(w, 'X'), /You already have a kicker/);
  assert.deepEqual(simSingletonWarnings(me, them, ['mk', 'mw'], ['tk']), []);
  const both = simSingletonWarnings(me, them, ['mk'], ['td', 'tw']);
  assert.deepEqual(both, [{ team: 'them', pos: 'K' }, { team: 'you', pos: 'DEF' }]);
  assert.match(simSingletonMessage(both, 'Z'), /You already have a defense.*Z already has a kicker/);
  assert.deepEqual(simSingletonWarnings(me, them, ['mw'], ['tw']), []);
});

test('a kicker cannot be seeded into a trade on a save from before kd_v', () => {
  const k = { id: 'tk', pos: 'K', owner: { type: 'team', team_id: 't1' } } as never;
  assert.equal(simTradeSeedFor(k, { kd_v: 0 }), null);
  assert.deepEqual(simTradeSeedFor(k, { kd_v: 1 }), { partner: 't1', get: 'tk' });
});

test('pos_v: kickers and defenses can be blocked only with pos_v 1 (and kd_v 1)', () => {
  assert.equal(simBlockable({ kd_v: 1, pos_v: 1 }, 'K'), true);
  assert.equal(simBlockable({ kd_v: 1, pos_v: 1 }, 'DEF'), true);
  assert.equal(simBlockable({ kd_v: 1 }, 'K'), false);
  assert.equal(simBlockable({ kd_v: 1 }, 'WR'), true);
});

test('pos_v: the one-per-team warning only exists before pos_v', () => {
  assert.equal(simSingletonRuleOn({ kd_v: 1 }), true);
  assert.equal(simSingletonRuleOn({ kd_v: 1, pos_v: 1 }), false);
  assert.equal(simSingletonRuleOn({}), false);
});

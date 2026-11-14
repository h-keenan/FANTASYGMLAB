// Run with: node --experimental-strip-types --test src/lib/simRosterLimit.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simAdvanceBlockers, simGameReasonMessage, simLimitBlocks, simOffseasonCta, simOverLimitNote } from './simGame.ts';
import { simAdvanceState, simTradeFit } from './simLayout.ts';

const game = (pending: Record<string, unknown>) => ({ pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 23, roster_limit: 18, cuts_needed: 5, ...pending } }) as never;

test('an old save or old server (limit_blocks absent) still blocks Advance when over the limit', () => {
  assert.equal(simLimitBlocks({}), true);
  assert.equal(simAdvanceState({ week: 3, pending: { cuts_needed: 5 } }, 0).blocked, true);
  assert.equal(simAdvanceBlockers(game({})).length, 1);
});

test('a soft-limit save is never blocked by the overage', () => {
  assert.equal(simLimitBlocks({ limit_blocks: false }), false);
  assert.equal(simAdvanceState({ week: 3, pending: { cuts_needed: 5, limit_blocks: false } }, 0).blocked, false);
  assert.deepEqual(simAdvanceBlockers(game({ limit_blocks: false })), []);
});

test('the offseason button reads Start season with a note instead of Finish cut-down', () => {
  const soft = simOffseasonCta({ stage: 'cutdown', season_no: 1, roster: { size: 23, limit: 18, cuts_needed: 5, limit_blocks: false } } as never);
  assert.deepEqual(soft, { action: 'start_season', label: 'Start season 2', blocked: null, note: 'Over the limit by 5: cut or trade to add players.' });
  const old = simOffseasonCta({ stage: 'cutdown', season_no: 1, roster: { size: 23, limit: 18, cuts_needed: 5 } } as never);
  assert.equal(old.label, 'Finish cut-down');
});

test('copy for the add-while-over error', () => {
  assert.equal(simGameReasonMessage('roster_full', { over_by: 3 }), simOverLimitNote(3));
});

test('trade builder count agrees with the server rule (active only, blocked only when adding past the limit)', () => {
  assert.equal(simTradeFit(18, 18, 1, 2, true).blocked, true);
  assert.equal(simTradeFit(23, 18, 2, 2, true).blocked, false);
  assert.equal(simTradeFit(23, 18, 3, 1, true).blocked, false);
  assert.equal(simTradeFit(23, 18, 1, 2, true).blocked, true);
  assert.deepEqual(simTradeFit(16, 18, 1, 3, true), { after: 18, room: 0, over: 0, blocked: false });
  assert.equal(simTradeFit(18, 18, 1, 2).blocked, false);
});

// Run with: node --experimental-strip-types --test src/lib/simGameCall.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { runSimGameCall } from './simGameCall.ts';
import { simApplyTradeSeed, simTradeSeedFor } from './simGame.ts';
import { simScrollKey, simShouldScrollTop, simTabAfterStageAction } from './simScroll.ts';

function handlers() {
  const log = { gates: [] as string[], errors: [] as string[] };
  return {
    log,
    h: { onGate: (g: { kind: string }) => log.gates.push(g.kind), onError: (m: string) => log.errors.push(m), retryMs: 0 },
  };
}

test('a storage failure on an action retries once and then succeeds without a gate', async () => {
  const { log, h } = handlers();
  let calls = 0;
  const body = await runSimGameCall(async () => (++calls === 1 ? { reason: 'sim_storage_unavailable', detail: 'http_5xx' } : { reason: '' }), h);
  assert.deepEqual(body, { reason: '' });
  assert.equal(calls, 2);
  assert.deepEqual(log, { gates: [], errors: [] });
});

test('a persistent storage failure is an inline error, never a full-screen gate', async () => {
  const { log, h } = handlers();
  const body = await runSimGameCall(async () => ({ reason: 'sim_storage_unavailable', detail: 'constraint' }), h);
  assert.equal(body, null);
  assert.deepEqual(log.gates, []);
  assert.match(log.errors[0], /Couldn't save that.*\(constraint\)/);
});

test('flag-off and conflicts keep their gates', async () => {
  const off = handlers();
  await runSimGameCall(async () => { throw { status: 404 }; }, off.h);
  assert.deepEqual(off.log.gates, ['unavailable']);
  const conflict = handlers();
  await runSimGameCall(async () => ({ reason: 'conflict' }), conflict.h);
  assert.deepEqual(conflict.log.gates, ['conflict']);
});

test('Add to trade seeds: mine go on the give side, an AI team\'s player picks that partner, free agents cannot be traded; adding is idempotent', () => {
  assert.equal(simTradeSeedFor({ id: 'f', owner: { type: 'free_agent' } }), null);
  assert.deepEqual(simTradeSeedFor({ id: 'm', owner: { type: 'you', team_id: '3' } }), { partner: '', give: 'm' });
  assert.deepEqual(simTradeSeedFor({ id: 'a', owner: { type: 'ai', team_id: '7' } }), { partner: '7', get: 'a' });
  let draft = simApplyTradeSeed({ partner: null, give: [], get: [] }, { partner: '7', get: 'a' });
  assert.deepEqual(draft, { partner: '7', give: [], get: ['a'] });
  draft = simApplyTradeSeed(draft, { partner: '', give: 'm' });
  draft = simApplyTradeSeed(draft, { partner: '', give: 'm' });
  assert.deepEqual(draft, { partner: '7', give: ['m'], get: ['a'] });
  // a different partner clears the incoming side but keeps what I give
  assert.deepEqual(simApplyTradeSeed(draft, { partner: '9', get: 'z' }), { partner: '9', give: ['m'], get: ['z'] });
  // sides cap
  assert.deepEqual(simApplyTradeSeed({ partner: '7', give: ['x'], get: [] }, { partner: '', give: 'y' }, 1).give, ['x']);
});

test('a page change scrolls to the top; the same page and the first render never do', () => {
  const week = simScrollKey({ view: 'game', stage: 'week', tab: 'home', week: 4, status: 'in_season' });
  const recap = simScrollKey({ view: 'game', stage: 'week', tab: 'home', week: 5, status: 'in_season', hasRecap: true, recapIndex: 0 });
  const nextRecap = simScrollKey({ view: 'game', stage: 'week', tab: 'home', week: 5, status: 'in_season', hasRecap: true, recapIndex: 1 });
  const tab = simScrollKey({ view: 'game', stage: 'week', tab: 'team', week: 5, status: 'in_season' });
  const offseason = simScrollKey({ view: 'game', stage: 'offseason', tab: 'home', week: 14, status: 'offseason' });
  assert.equal(simShouldScrollTop(null, week), false);
  assert.equal(simShouldScrollTop(week, week), false);
  for (const next of [recap, nextRecap, tab, offseason]) assert.equal(simShouldScrollTop(week, next), true);
  assert.equal(simShouldScrollTop(recap, nextRecap), true);
});

test('stage-advancing actions land on the page that hosts the new stage, and a new offseason step scrolls to the top', () => {
  for (const action of ['start_rookie_draft', 'auto_draft', 'start_season', 'start_playoffs'] as const) assert.equal(simTabAfterStageAction(action), 'home');
  const review = simScrollKey({ view: 'game', stage: 'offseason', tab: 'home', status: 'offseason', step: 'review' });
  const draft = simScrollKey({ view: 'game', stage: 'offseason', tab: 'home', status: 'offseason', step: 'rookie_draft' });
  assert.equal(simShouldScrollTop(review, draft), true);
});

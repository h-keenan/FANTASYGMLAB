// Run with: node --experimental-strip-types --test src/lib/portfolioLoader.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import type { PortfolioLeagueResponse } from './api.ts';
import type { PortfolioLeagueState } from './portfolioProgress.ts';
import {
  PORTFOLIO_EAGER_LEAGUES,
  PORTFOLIO_LEAGUE_CONCURRENCY,
  PORTFOLIO_ROW_MIN_HEIGHT,
  PORTFOLIO_SHELL_SKELETON_COUNT,
  PORTFOLIO_SPLASH_DELAY_MS,
  startLeagueLoader,
} from './portfolioLoader.ts';

function response(id: string, signalsPending = false): PortfolioLeagueResponse {
  return {
    ok: true,
    is_premium: true,
    lens: 'Dynasty',
    league: null,
    failed_league: null,
    upsell: null,
    _id: id,
    ...(signalsPending ? { signals_pending: true } : {}),
  } as never;
}

/** A load() whose promises the test resolves/rejects by hand. */
function controllable() {
  const calls: string[] = [];
  const phases: string[] = [];
  const pending = new Map<string, { resolve: (v: PortfolioLeagueResponse) => void; reject: (e: unknown) => void }>();
  let inFlight = 0;
  let maxInFlight = 0;
  const signals = new Map<string, AbortSignal>();
  const load = (id: string, signal: AbortSignal, phase: string = 'headline') => {
    calls.push(id);
    phases.push(`${id}:${phase}`);
    signals.set(id, signal);
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    return new Promise<PortfolioLeagueResponse>((resolve, reject) => {
      pending.set(id, {
        resolve: (v) => {
          inFlight -= 1;
          resolve(v);
        },
        reject: (e) => {
          inFlight -= 1;
          reject(e);
        },
      });
    });
  };
  return { load, calls, phases, pending, signals, maxInFlight: () => maxInFlight };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

test('starts leagues in saved order and never exceeds the concurrency cap', async () => {
  const c = controllable();
  const ids = ['a', 'b', 'c', 'd', 'e', 'f'];
  const states: Record<string, PortfolioLeagueState> = {};
  startLeagueLoader({ leagueIds: ids, load: c.load, onState: (id, s) => (states[id] = s) });
  assert.equal(PORTFOLIO_LEAGUE_CONCURRENCY, 3);
  assert.deepEqual(c.calls, ['a', 'b', 'c']);
  for (const id of ids) {
    await flush();
    c.pending.get(id)?.resolve(response(id));
    await flush();
  }
  assert.deepEqual(c.calls, ids);
  assert.ok(c.maxInFlight() <= PORTFOLIO_LEAGUE_CONCURRENCY);
  assert.ok(Object.values(states).every((s) => s.status === 'success'));
});

test('one failed league does not block the others and can be retried alone', async () => {
  const c = controllable();
  const states: Record<string, PortfolioLeagueState> = {};
  const loader = startLeagueLoader({
    leagueIds: ['a', 'b', 'c', 'd'],
    load: c.load,
    onState: (id, s) => (states[id] = s),
    concurrency: 2,
  });
  c.pending.get('a')?.reject(new Error('boom'));
  await flush();
  assert.deepEqual(states.a, { status: 'error' });
  assert.deepEqual(c.calls, ['a', 'b', 'c']);
  c.pending.get('b')?.resolve(response('b'));
  c.pending.get('c')?.resolve(response('c'));
  await flush();
  c.pending.get('d')?.resolve(response('d'));
  await flush();
  loader.retry('a');
  assert.deepEqual(states.a, { status: 'pending' });
  assert.equal(c.calls.filter((id) => id === 'a').length, 2);
  c.pending.get('a')?.resolve(response('a'));
  await flush();
  assert.equal(states.a.status, 'success');
});

test('abort cancels in-flight requests, drops the queue and stops state updates', async () => {
  const c = controllable();
  const seen: string[] = [];
  const loader = startLeagueLoader({ leagueIds: ['a', 'b', 'c', 'd', 'e'], load: c.load, onState: (id) => seen.push(id) });
  loader.abort();
  assert.equal(c.signals.get('a')?.aborted, true);
  c.pending.get('a')?.resolve(response('a'));
  await flush();
  assert.deepEqual(seen, []);
  assert.deepEqual(c.calls, ['a', 'b', 'c']);
});

test('loads only the eager window until unlocked, then releases leagues in saved order', async () => {
  const c = controllable();
  const ids = Array.from({ length: 9 }, (_, i) => `l${i}`);
  const loader = startLeagueLoader({ leagueIds: ids, load: c.load, onState: () => {} });
  for (let i = 0; i < PORTFOLIO_EAGER_LEAGUES; i += 1) {
    await flush();
    c.pending.get(ids[i])?.resolve(response(ids[i]));
  }
  await flush();
  assert.deepEqual(c.calls, ids.slice(0, PORTFOLIO_EAGER_LEAGUES));
  loader.unlock(2);
  await flush();
  assert.deepEqual(c.calls, ids.slice(0, PORTFOLIO_EAGER_LEAGUES + 2));
  loader.unlockAll();
  await flush();
  assert.deepEqual(c.calls, ids);
});

test("queues every league's headline ahead of any league's full request", async () => {
  const c = controllable();
  const states: Record<string, PortfolioLeagueState> = {};
  startLeagueLoader({
    leagueIds: ['a', 'b', 'c', 'd'],
    load: c.load,
    onState: (id, s) => (states[id] = s),
    concurrency: 2,
  });
  assert.deepEqual(c.phases, ['a:headline', 'b:headline']);
  c.pending.get('a')?.resolve(response('a', true));
  await flush();
  assert.deepEqual(c.phases, ['a:headline', 'b:headline', 'c:headline']);
  c.pending.get('b')?.resolve(response('b', true));
  await flush();
  assert.deepEqual(c.phases.slice(3), ['d:headline']);
  c.pending.get('c')?.resolve(response('c', true));
  c.pending.get('d')?.resolve(response('d', true));
  await flush();
  assert.deepEqual(c.phases.slice(4), ['a:full', 'b:full']);
  const a = states.a;
  assert.ok(a.status === 'success' && a.data.signals_pending);
  c.pending.get('a')?.resolve(response('a'));
  await flush();
  const a2 = states.a;
  assert.ok(a2.status === 'success' && !a2.data.signals_pending);
  assert.deepEqual(c.phases.slice(6), ['c:full']);
});

test('a complete headline (server had it cached) is final: no second request', async () => {
  const c = controllable();
  startLeagueLoader({ leagueIds: ['a'], load: c.load, onState: () => {} });
  c.pending.get('a')?.resolve(response('a'));
  await flush();
  assert.deepEqual(c.phases, ['a:headline']);
});

test('revalidates warm leagues with one full request and leaves fresh ones alone', () => {
  const c = controllable();
  startLeagueLoader({ leagueIds: ['a', 'b', 'c'], load: c.load, onState: () => {}, warm: ['b'], skip: ['c'] });
  assert.deepEqual(c.phases, ['a:headline', 'b:full']);
});

test('a failed revalidation never blanks the stale data on screen', async () => {
  const c = controllable();
  const seen: string[] = [];
  startLeagueLoader({ leagueIds: ['a'], load: c.load, onState: (id) => seen.push(id), warm: ['a'] });
  c.pending.get('a')?.reject(new Error('offline'));
  await flush();
  assert.deepEqual(seen, []);
});

test('retry on a window-locked league releases it', async () => {
  const c = controllable();
  const seen: Array<[string, string]> = [];
  const loader = startLeagueLoader({
    leagueIds: ['a', 'b', 'c'],
    load: c.load,
    onState: (id, s) => seen.push([id, s.status]),
    eager: 1,
  });
  assert.deepEqual(c.calls, ['a']);
  loader.retry('c');
  await flush();
  assert.ok(c.calls.includes('c'));
  assert.deepEqual(seen, []);
});

test('constants: cap is 2-3, splash only after ~300ms, rows reserve height', () => {
  assert.ok(PORTFOLIO_LEAGUE_CONCURRENCY >= 2 && PORTFOLIO_LEAGUE_CONCURRENCY <= 3);
  assert.equal(PORTFOLIO_SPLASH_DELAY_MS, 300);
  assert.ok(PORTFOLIO_ROW_MIN_HEIGHT > 0);
  assert.ok(PORTFOLIO_SHELL_SKELETON_COUNT >= 1);
});

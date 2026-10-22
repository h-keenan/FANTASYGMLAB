// Run with: node --experimental-strip-types --test src/lib/analyticsCore.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANON_ID_KEY,
  QUEUE_KEY,
  createAnalytics,
  parseAnalyticsFlag,
  sanitizeProps,
  type AnalyticsEvent,
} from './analyticsCore.ts';

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: async (k: string) => data.get(k) ?? null,
    setItem: async (k: string, v: string) => {
      data.set(k, v);
    },
  };
}

function make(opts: { enabled?: boolean; failSend?: boolean; storage?: ReturnType<typeof memoryStorage>; maxQueue?: number; batchSize?: number } = {}) {
  const sent: AnalyticsEvent[] = [];
  const state = { enabled: opts.enabled ?? true, failSend: opts.failSend ?? false };
  const storage = opts.storage ?? memoryStorage();
  const a = createAnalytics({
    enabled: () => state.enabled,
    send: async (e) => {
      if (state.failSend) throw new TypeError('Network request failed');
      sent.push(e);
    },
    storage,
    platform: 'ios',
    randomId: () => 'abcdef0123456789',
    maxQueue: opts.maxQueue,
    batchSize: opts.batchSize,
  });
  return { a, sent, state, storage };
}

test('parseAnalyticsFlag: defaults OFF, only explicit truthy values enable', () => {
  assert.equal(parseAnalyticsFlag(undefined), false);
  assert.equal(parseAnalyticsFlag(''), false);
  assert.equal(parseAnalyticsFlag('0'), false);
  assert.equal(parseAnalyticsFlag('maybe'), false);
  assert.equal(parseAnalyticsFlag('1'), true);
  assert.equal(parseAnalyticsFlag(' TRUE '), true);
});

test('kill switch: disabled queues, stores and sends nothing', async () => {
  const { a, sent, storage } = make({ enabled: false });
  a.track('feature_use', { feature: 'x', action: 'y' });
  a.trackScreen('Home');
  await a.flush();
  assert.equal(a.queueSize(), 0);
  assert.equal(sent.length, 0);
  assert.equal(storage.data.size, 0);
});

test('trackUse emits feature_use with web-compatible props plus platform', async () => {
  const { a, sent } = make();
  a.trackUse('percentile_explorer', 'opened', { tier: 'pro', leagueId: 'L1', props: { item_kind: 'rush_yds' } });
  await a.flush();
  assert.equal(sent.length, 1);
  assert.equal(sent[0].event, 'feature_use');
  assert.deepEqual(sent[0].props, {
    item_kind: 'rush_yds',
    feature: 'percentile_explorer',
    action: 'opened',
    tier: 'pro',
    league_id: 'L1',
    platform: 'ios',
  });
  assert.match(sent[0].anon_id, /^anon_/);
});

test('trackScreen sends page_view with a mobile/ route name only', async () => {
  const { a, sent } = make();
  a.trackScreen('TradeHub');
  await a.flush();
  assert.equal(sent[0].event, 'page_view');
  assert.equal(sent[0].props.route, 'mobile/TradeHub');
  assert.equal(sent[0].props.platform, 'ios');
});

test('sanitizeProps drops non-allowlisted and sensitive keys and non-primitive values', () => {
  const clean = sanitizeProps({
    feature: 'x',
    email: 'a@b.com',
    access_token: 'secret',
    player_name: 'Someone',
    nested: { a: 1 },
    result: 'ok',
    action: 'z'.repeat(500),
  });
  assert.deepEqual(Object.keys(clean).sort(), ['action', 'feature', 'result']);
  assert.equal((clean.action as string).length, 80);
});

test('anon id is minted once and persisted', async () => {
  const storage = memoryStorage();
  const { a } = make({ storage });
  a.track('session_started');
  await a.ready();
  assert.equal(storage.data.get(ANON_ID_KEY), 'anon_abcdef0123456789');
});

test('failing network never throws; events stay queued and are retried', async () => {
  const { a, sent, state } = make({ failSend: true });
  a.trackUse('f', 'a');
  a.trackUse('f', 'b');
  await assert.doesNotReject(a.flush());
  assert.equal(a.queueSize(), 2);
  assert.equal(sent.length, 0);
  state.failSend = false;
  await a.flush();
  assert.equal(a.queueSize(), 0);
  assert.deepEqual(sent.map((e) => e.props.action), ['a', 'b']);
});

test('batching: flush sends at most batchSize events per run, in order', async () => {
  const { a, sent } = make({ batchSize: 2 });
  for (const n of ['1', '2', '3']) a.trackUse('f', n);
  await a.flush();
  assert.equal(sent.length, 2);
  assert.equal(a.queueSize(), 1);
  await a.flush();
  assert.deepEqual(sent.map((e) => e.props.action), ['1', '2', '3']);
});

test('queue is bounded: oldest events are dropped past maxQueue', async () => {
  const { a } = make({ maxQueue: 3 });
  for (let i = 0; i < 10; i += 1) a.trackUse('f', String(i));
  assert.equal(a.queueSize(), 3);
});

test('offline queue survives a restart via storage', async () => {
  const storage = memoryStorage();
  const first = make({ storage, failSend: true });
  first.a.trackUse('f', 'offline');
  await first.a.flush();
  assert.ok(storage.data.get(QUEUE_KEY)?.includes('offline'));

  const second = make({ storage });
  await second.a.flush();
  assert.equal(second.sent.length, 1);
  assert.equal(second.sent[0].props.action, 'offline');
});

test('storage failures and a throwing enabled() never throw', async () => {
  const a = createAnalytics({
    enabled: () => {
      throw new Error('boom');
    },
    send: async () => {},
    storage: {
      getItem: async () => {
        throw new Error('x');
      },
      setItem: async () => {
        throw new Error('x');
      },
    },
    platform: 'android',
  });
  assert.doesNotThrow(() => a.track('feature_use'));
  await assert.doesNotReject(a.flush());

  const b = createAnalytics({
    enabled: () => true,
    send: async () => {
      throw new Error('down');
    },
    storage: {
      getItem: async () => {
        throw new Error('x');
      },
      setItem: async () => {
        throw new Error('x');
      },
    },
    platform: 'android',
  });
  b.track('feature_use');
  await assert.doesNotReject(b.flush());
});

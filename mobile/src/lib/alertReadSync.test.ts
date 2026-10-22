// Run with: node --experimental-strip-types --test src/lib/alertReadSync.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { createAlertReadSync, type AlertReadStorage } from './alertReadSync.ts';

function memoryStorage(): AlertReadStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    async getItem(key) {
      return data.get(key) ?? null;
    },
    async setItem(key, value) {
      data.set(key, value);
    },
  };
}

test('markRead clears the pending read once the server records it', async () => {
  const calls: string[] = [];
  const sync = createAlertReadSync(memoryStorage(), async (leagueId, key) => {
    calls.push(`${leagueId}:${key}`);
    return { ok: true };
  });
  assert.equal(await sync.markRead('u1', 'L1', 'k1'), true);
  assert.deepEqual(calls, ['L1:k1']);
  assert.equal((await sync.pendingKeys('u1', 'L1')).size, 0);
});

test('offline or ok:false keeps the read pending and shown as read, scoped per account+league', async () => {
  let attempt = 0;
  const sync = createAlertReadSync(memoryStorage(), async () => {
    attempt += 1;
    if (attempt === 1) throw new TypeError('Network request failed');
    return { ok: false };
  });
  assert.equal(await sync.markRead('u1', 'L1', 'k1'), false);
  assert.equal(await sync.markRead('u1', 'L1', 'k2'), false);
  assert.deepEqual([...(await sync.pendingKeys('u1', 'L1'))].sort(), ['k1', 'k2']);

  const overlaid = await sync.overlayPending('u1', 'L1', [
    { alert_key: 'k1', read: false },
    { alert_key: 'k3', read: false },
  ]);
  assert.deepEqual(overlaid, [
    { alert_key: 'k1', read: true },
    { alert_key: 'k3', read: false },
  ]);
  assert.equal((await sync.pendingKeys('u2', 'L1')).size, 0);
  assert.equal((await sync.pendingKeys('u1', 'L2')).size, 0);
});

test('reconcile drops server-confirmed reads and retries only the unsynced ones', async () => {
  const storage = memoryStorage();
  let online = false;
  const retried: string[] = [];
  const sync = createAlertReadSync(storage, async (_leagueId, key) => {
    if (!online) return { ok: false };
    retried.push(key);
    return { ok: true };
  });
  await sync.markRead('u1', 'L1', 'k1');
  await sync.markRead('u1', 'L1', 'k2');

  online = true;
  const merged = await sync.reconcile('u1', 'L1', [
    { alert_key: 'k1', read: true },
    { alert_key: 'k2', read: false },
  ]);
  assert.deepEqual(merged, [
    { alert_key: 'k1', read: true },
    { alert_key: 'k2', read: true },
  ]);
  // Let the background retry settle.
  for (let i = 0; i < 10 && (await sync.pendingKeys('u1', 'L1')).size > 0; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  assert.deepEqual(retried, ['k2']);
  assert.equal((await sync.pendingKeys('u1', 'L1')).size, 0);
});

test('a throwing storage degrades to server-only state', async () => {
  const broken: AlertReadStorage = {
    async getItem() {
      throw new Error('blocked');
    },
    async setItem() {
      throw new Error('blocked');
    },
  };
  const sync = createAlertReadSync(broken, async () => ({ ok: true }));
  assert.equal(await sync.markRead('u1', 'L1', 'k1'), true);
  assert.deepEqual(await sync.reconcile('u1', 'L1', [{ alert_key: 'k1', read: false }]), [
    { alert_key: 'k1', read: false },
  ]);
});

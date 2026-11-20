import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEVICE_LEVEL_KEYS,
  isAccountPurgeKey,
  migrateLegacyKeysAsync,
  planMigration,
  planPurge,
  purgeAsyncStore,
  userScopedKey,
  type AsyncKeyValueStore,
} from './accountScope.ts';
import { createUserStorage } from './userStorageCore.ts';

function memoryStore(initial: Record<string, string> = {}): AsyncKeyValueStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    async getAllKeys() {
      return [...data.keys()];
    },
    async getItem(key) {
      return data.has(key) ? (data.get(key) as string) : null;
    },
    async setItem(key, value) {
      data.set(key, value);
    },
    async removeItem(key) {
      data.delete(key);
    },
    async multiRemove(keys) {
      for (const key of keys) data.delete(key);
    },
  };
}

const SUPABASE = 'sb-abc-auth-token';

test('B never sees A after A signs out and B signs in', async () => {
  const store = memoryStore({ [SUPABASE]: 'tokens', 'fgl:theme-mode': 'dark', 'fgl:react-query-cache': '{}' });
  const us = createUserStorage(store);
  await us.applyUser('A');
  await us.set('fgl:last-league', '{"leagueId":"L1","leagueName":"Mine"}');
  await us.set('fgl:dashboard-seen-recs:L1', '["r1"]');
  assert.equal(await us.get('fgl:dashboard-seen-recs:L1'), '["r1"]');

  await us.purge();
  await us.applyUser(null);
  await us.applyUser('B');
  assert.equal(await us.get('fgl:last-league'), null);
  assert.equal(await us.get('fgl:dashboard-seen-recs:L1'), null);
  for (const key of store.data.keys()) assert.equal(key.startsWith('u:A:'), false);
  // Device preferences and Supabase's own auth storage survive the purge.
  assert.equal(store.data.get('fgl:theme-mode'), 'dark');
  assert.equal(store.data.get(SUPABASE), 'tokens');
});

test('a switch A to B without a sign-out is isolated by the key scope even before the purge runs', async () => {
  const store = memoryStore();
  const us = createUserStorage(store);
  await us.applyUser('A');
  await us.set('fgl:trade-hub-seen:L1', '4');
  await us.applyUser('B');
  assert.equal(await us.get('fgl:trade-hub-seen:L1'), null);
  await us.applyUser('A');
  assert.equal(await us.get('fgl:trade-hub-seen:L1'), '4');
});

test('nobody signed in: reads are null and writes are dropped', async () => {
  const store = memoryStore();
  const us = createUserStorage(store);
  await us.set('fgl:last-league', 'x');
  assert.equal(await us.get('fgl:last-league'), null);
  assert.equal(store.data.size, 0);
});

test('a migrated user loses nothing; the plain keys are deleted; a second user gets none', async () => {
  const legacy: Record<string, string> = {
    'fgl:last-league': '{"leagueId":"L1","leagueName":"Mine"}',
    'fgl:dashboard-seen-recs:L1': '["r1","r2"]',
    'fgl:trade-hub-seen:L1': '3',
    'fgl:recap-opened:L1': 'recap-9',
    'fgl:compare-recent:L1': '["p1"]',
    'fgl:trial-lapsed-shown-expiration': '2026-11-01',
    'fgl:guess-the-player-dismissed-pick-id': 'pick-1',
    'fgl:guess-the-player-name-match-dismissed-pick-id': 'pair-1',
    'fgl:sim-notif-read:g1': '7',
    'fgl:sim-rookie-notice:g1': '1',
    'sim.realism.banner.g1.2.a': '1',
  };
  const store = memoryStore({ ...legacy, 'fgl:theme-mode': 'light' });
  const us = createUserStorage(store);
  await us.applyUser('A');
  for (const [key, value] of Object.entries(legacy)) {
    assert.equal(await us.get(key), value, `lost ${key}`);
    assert.equal(store.data.has(key), false, `plain key left: ${key}`);
  }
  assert.equal(store.data.get('fgl:theme-mode'), 'light');
  await us.applyUser('B');
  for (const key of Object.keys(legacy)) assert.equal(await us.get(key), null);
});

test('migration is idempotent and an existing scoped value wins', async () => {
  const store = memoryStore({ 'fgl:last-league': 'old', 'u:A:fgl:last-league': 'new' });
  assert.equal(await migrateLegacyKeysAsync(store, 'A'), 1);
  assert.equal(store.data.get('u:A:fgl:last-league'), 'new');
  assert.equal(store.data.has('fgl:last-league'), false);
  assert.equal(await migrateLegacyKeysAsync(store, 'A'), 0);
});

test('a read right after sign-in waits for the migration', async () => {
  const store = memoryStore({ 'fgl:last-league': 'mine' });
  const us = createUserStorage(store);
  const applying = us.applyUser('A');
  assert.equal(await us.get('fgl:last-league'), 'mine');
  await applying;
});

test('purge removes scoped keys, unscoped account keys and leftover plain keys, never device keys', async () => {
  const store = memoryStore({
    'u:A:fgl:last-league': 'x',
    'fgl:last-league': 'y',
    'fgl:dashboard-seen-recs:L9': 'z',
    [SUPABASE]: 'tokens',
  });
  for (const { key } of DEVICE_LEVEL_KEYS) if (!key.endsWith(':')) store.data.set(key, 'keep');
  const removed = await purgeAsyncStore(store);
  assert.equal(removed, 3);
  for (const { key } of DEVICE_LEVEL_KEYS) if (!key.endsWith(':')) assert.equal(store.data.get(key), 'keep');
  assert.equal(store.data.get(SUPABASE), 'tokens');
});

test('kill switch off: plain keys, no migration, no purge', async () => {
  const store = memoryStore({ 'fgl:last-league': 'y', 'u:A:x': '1' });
  const us = createUserStorage(store, false);
  await us.applyUser('A');
  assert.equal(await us.get('fgl:last-league'), 'y');
  await us.purge();
  assert.equal(store.data.get('u:A:x'), '1');
  assert.equal(userScopedKey('A', 'k', false), 'k');
  assert.deepEqual(planPurge(['u:A:x'], false), []);
  assert.deepEqual(planMigration(['fgl:last-league'], false), []);
});

test('no device-level key is also a purge key', () => {
  for (const { key } of DEVICE_LEVEL_KEYS) assert.equal(isAccountPurgeKey(key), false, key);
});

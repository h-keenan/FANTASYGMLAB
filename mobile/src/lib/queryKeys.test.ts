// Run with: node --experimental-strip-types --test src/lib/queryKeys.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { QueryClient } from '@tanstack/react-query';

import { setCurrentAuthScopeUserId } from './authScope.ts';
import { queryKeys } from './queryKeys.ts';

test('queryKeys: two different users requesting the same league id get different keys', () => {
  setCurrentAuthScopeUserId('user-a');
  const aliceKey = queryKeys.dashboard('league-123');

  setCurrentAuthScopeUserId('user-b');
  const bobKey = queryKeys.dashboard('league-123');

  assert.notDeepEqual(aliceKey, bobKey);
  assert.deepEqual(aliceKey, ['user', 'user-a', 'league', 'league-123', 'dashboard']);
  assert.deepEqual(bobKey, ['user', 'user-b', 'league', 'league-123', 'dashboard']);

  setCurrentAuthScopeUserId(null);
});

test('queryKeys: user A -> user B cannot read back user A\'s cached server data for the same league id', () => {
  const client = new QueryClient();

  setCurrentAuthScopeUserId('user-a');
  client.setQueryData(queryKeys.dashboard('league-123'), { headline: "Alice's private dashboard data" });
  assert.deepEqual(client.getQueryData(queryKeys.dashboard('league-123')), {
    headline: "Alice's private dashboard data",
  });

  setCurrentAuthScopeUserId('user-b');
  // Same league id, different (now-current) user — must not see Alice's data.
  assert.equal(client.getQueryData(queryKeys.dashboard('league-123')), undefined);

  setCurrentAuthScopeUserId(null);
  client.clear();
});

test('queryKeys: same user, same league id -> same key (cache-first behavior preserved)', () => {
  setCurrentAuthScopeUserId('user-a');
  const first = queryKeys.myTeam('league-456');
  const second = queryKeys.myTeam('league-456');
  assert.deepEqual(first, second);
  setCurrentAuthScopeUserId(null);
});

test('queryKeys: every factory is scoped under the current user, not just league-keyed ones', () => {
  setCurrentAuthScopeUserId('user-a');
  assert.deepEqual(queryKeys.playerQuickView('player-1'), [
    'user',
    'user-a',
    'player-quick-view',
    'player-1',
  ]);
  setCurrentAuthScopeUserId(null);
});

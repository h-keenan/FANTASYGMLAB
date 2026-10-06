// Run with: node --experimental-strip-types --test src/lib/queryClient.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { QueryClient } from '@tanstack/react-query';
import {
  persistQueryClientRestore,
  persistQueryClientSave,
  type Persister,
} from '@tanstack/query-persist-client-core';

import {
  clearAuthenticatedQueryCache,
  PERSISTED_QUERY_CACHE_VERSION,
} from './queryClient.ts';

/** Trivial in-memory stand-in for the real AsyncStorage-backed persister —
 * same shape (`persistClient`/`restoreClient`/`removeClient`), no RN/storage
 * dependency, so these tests can run under plain `node --test`. */
function createInMemoryPersister() {
  let stored: Parameters<Persister['persistClient']>[0] | undefined;
  let removeClientCalls = 0;

  const persister: Persister = {
    persistClient: (client) => {
      stored = client;
    },
    restoreClient: () => stored,
    removeClient: () => {
      stored = undefined;
      removeClientCalls += 1;
    },
  };

  return {
    persister,
    get removeClientCalls() {
      return removeClientCalls;
    },
  };
}

test('clearAuthenticatedQueryCache: clears the in-memory client and calls persister.removeClient', async () => {
  const client = new QueryClient();
  client.setQueryData(['user', 'user-a', 'league', '123', 'dashboard'], { foo: 1 });
  assert.ok(client.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']));

  const fakePersister = createInMemoryPersister();
  await fakePersister.persister.persistClient({
    timestamp: Date.now(),
    buster: PERSISTED_QUERY_CACHE_VERSION,
    clientState: { queries: [], mutations: [] },
  });

  await clearAuthenticatedQueryCache(client, fakePersister.persister);

  assert.equal(client.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']), undefined);
  assert.equal(client.getQueryCache().getAll().length, 0);
  assert.equal(fakePersister.removeClientCalls, 1);
});

test('clearAuthenticatedQueryCache: cancels in-flight queries so they cannot repopulate the cache after clearing', async () => {
  const client = new QueryClient();
  let resolveFetch: ((value: { foo: number }) => void) | undefined;
  const pending = new Promise<{ foo: number }>((resolve) => {
    resolveFetch = resolve;
  });

  const fetchPromise = client.fetchQuery({
    queryKey: ['user', 'user-a', 'league', '123', 'dashboard'],
    queryFn: () => pending,
  });

  const { persister } = createInMemoryPersister();
  await clearAuthenticatedQueryCache(client, persister);

  // Resolve the outgoing user's in-flight request AFTER the clear — it must
  // not be able to write its result back into the cache.
  resolveFetch?.({ foo: 1 });
  await fetchPromise.catch(() => {}); // a cancelled query rejects; that's expected here

  assert.equal(client.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']), undefined);
});

test('clearAuthenticatedQueryCache: a persister failure never throws / never blocks completing the clear', async () => {
  const client = new QueryClient();
  client.setQueryData(['user', 'user-a', 'league', '123', 'dashboard'], { foo: 1 });

  const brokenPersister: Persister = {
    persistClient: async () => {},
    restoreClient: async () => undefined,
    removeClient: async () => {
      throw new Error('AsyncStorage unavailable');
    },
  };

  await assert.doesNotReject(clearAuthenticatedQueryCache(client, brokenPersister));
  // The in-memory clear must still have happened even though the persister
  // step failed — a cache-clear failure must never leave stale data behind
  // or block the caller (e.g. sign-out) from completing.
  assert.equal(client.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']), undefined);
});

test('cache buster: a mismatched buster discards an older persisted cache instead of restoring it', async () => {
  const writerClient = new QueryClient();
  writerClient.setQueryData(['user', 'user-a', 'league', '123', 'dashboard'], {
    headline: 'stale, pre-update payload shape',
  });

  const fakePersister = createInMemoryPersister();
  await persistQueryClientSave({
    queryClient: writerClient,
    persister: fakePersister.persister,
    buster: 'old-version',
  });

  const readerClient = new QueryClient();
  await persistQueryClientRestore({
    queryClient: readerClient,
    persister: fakePersister.persister,
    buster: PERSISTED_QUERY_CACHE_VERSION,
  });

  assert.equal(
    readerClient.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']),
    undefined,
  );
  assert.equal(fakePersister.removeClientCalls, 1);
});

test('cache buster: a matching buster still restores normally (ordinary restart keeps its cache)', async () => {
  const writerClient = new QueryClient();
  writerClient.setQueryData(['user', 'user-a', 'league', '123', 'dashboard'], {
    headline: 'current payload shape',
  });

  const fakePersister = createInMemoryPersister();
  await persistQueryClientSave({
    queryClient: writerClient,
    persister: fakePersister.persister,
    buster: PERSISTED_QUERY_CACHE_VERSION,
  });

  const readerClient = new QueryClient();
  await persistQueryClientRestore({
    queryClient: readerClient,
    persister: fakePersister.persister,
    buster: PERSISTED_QUERY_CACHE_VERSION,
  });

  assert.deepEqual(readerClient.getQueryData(['user', 'user-a', 'league', '123', 'dashboard']), {
    headline: 'current payload shape',
  });
});

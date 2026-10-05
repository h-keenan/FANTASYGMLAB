// Run with: node --experimental-strip-types --test src/lib/authScope.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANONYMOUS_QUERY_SCOPE,
  AUTH_SCOPE_STORAGE_KEY,
  didAuthenticatedUserChange,
  getCurrentAuthScopeUserId,
  readStoredAuthScopeUserId,
  setCurrentAuthScopeUserId,
  userScopeKey,
  writeStoredAuthScopeUserId,
  type AuthScopeStorage,
} from './authScope.ts';

function fakeStorage(initial: Record<string, string> = {}): AuthScopeStorage & {
  data: Record<string, string>;
} {
  const data: Record<string, string> = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
    removeItem: (key) => {
      delete data[key];
    },
  };
}

test('didAuthenticatedUserChange: user A -> user B is a change', () => {
  assert.equal(didAuthenticatedUserChange('user-a', 'user-b'), true);
});

test('didAuthenticatedUserChange: same user id (e.g. a token refresh) is NOT a change', () => {
  assert.equal(didAuthenticatedUserChange('user-a', 'user-a'), false);
});

test('didAuthenticatedUserChange: no prior recorded user (fresh install / proper prior sign-out) is NOT a change', () => {
  assert.equal(didAuthenticatedUserChange(null, 'user-b'), false);
});

test('didAuthenticatedUserChange: signing out (next is null) is NOT a change handled here', () => {
  // Normal sign-out clears the cache explicitly elsewhere (AuthContext's
  // signOut) — this comparison only exists to catch a *different* concrete
  // user becoming authenticated.
  assert.equal(didAuthenticatedUserChange('user-a', null), false);
});

test('userScopeKey: anonymous before any user is set', () => {
  setCurrentAuthScopeUserId(null);
  assert.deepEqual(userScopeKey(), ['user', ANONYMOUS_QUERY_SCOPE]);
  assert.equal(getCurrentAuthScopeUserId(), null);
});

test('userScopeKey: reflects the currently-set user id', () => {
  setCurrentAuthScopeUserId('user-a');
  assert.deepEqual(userScopeKey(), ['user', 'user-a']);
  assert.equal(getCurrentAuthScopeUserId(), 'user-a');
  setCurrentAuthScopeUserId(null); // reset for any later test in this file
});

test('readStoredAuthScopeUserId / writeStoredAuthScopeUserId: round-trip through a fake storage', async () => {
  const storage = fakeStorage();
  assert.equal(await readStoredAuthScopeUserId(storage), null);

  await writeStoredAuthScopeUserId(storage, 'user-a');
  assert.equal(storage.data[AUTH_SCOPE_STORAGE_KEY], 'user-a');
  assert.equal(await readStoredAuthScopeUserId(storage), 'user-a');

  await writeStoredAuthScopeUserId(storage, null);
  assert.equal(AUTH_SCOPE_STORAGE_KEY in storage.data, false);
  assert.equal(await readStoredAuthScopeUserId(storage), null);
});

test('readStoredAuthScopeUserId: a storage failure reads as "nothing recorded," never throws', async () => {
  const storage: AuthScopeStorage = {
    getItem: () => {
      throw new Error('storage unavailable');
    },
    setItem: () => {},
    removeItem: () => {},
  };
  assert.equal(await readStoredAuthScopeUserId(storage), null);
});

test('writeStoredAuthScopeUserId: a storage failure never throws', async () => {
  const storage: AuthScopeStorage = {
    getItem: () => null,
    setItem: () => {
      throw new Error('storage unavailable');
    },
    removeItem: () => {
      throw new Error('storage unavailable');
    },
  };
  await assert.doesNotReject(writeStoredAuthScopeUserId(storage, 'user-a'));
  await assert.doesNotReject(writeStoredAuthScopeUserId(storage, null));
});

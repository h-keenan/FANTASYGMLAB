import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  BAD_RESPONSE_MESSAGE,
  FORBIDDEN_MESSAGE,
  SERVER_ERROR_MESSAGE,
  classifyErrorMessage,
  friendlyStatusMessage,
  isRetryableSessionLookupError,
} from './badDayCopy.ts';
import { clearSessionEnded, isForcedSignOut, markSessionEnded, readSessionEnded } from './sessionEnded.ts';

test('only an unrequested SIGNED_OUT that ended a real session is forced', () => {
  assert.equal(isForcedSignOut({ event: 'SIGNED_OUT', hadSession: true, userInitiated: false }), true);
  assert.equal(isForcedSignOut({ event: 'SIGNED_OUT', hadSession: true, userInitiated: true }), false);
  assert.equal(isForcedSignOut({ event: 'SIGNED_OUT', hadSession: false, userInitiated: false }), false);
  assert.equal(isForcedSignOut({ event: 'TOKEN_REFRESHED', hadSession: true, userInitiated: false }), false);
});

test('the session-ended marker expires and clears', () => {
  const store = new Map<string, string>();
  const storage = {
    setItem: (k: string, v: string) => void store.set(k, v),
    getItem: (k: string) => store.get(k) ?? null,
    removeItem: (k: string) => void store.delete(k),
  };
  markSessionEnded(storage, 1_000);
  assert.equal(readSessionEnded(storage, 2_000), true);
  assert.equal(readSessionEnded(storage, 1_000 + 2 * 60 * 60 * 1000), false);
  clearSessionEnded(storage);
  assert.equal(readSessionEnded(storage, 2_000), false);
});

test('status messages for auth and proxy failures', () => {
  assert.equal(friendlyStatusMessage(401, 'Invalid or expired session.'), 'Not signed in.');
  assert.equal(classifyErrorMessage(friendlyStatusMessage(401, 'Invalid or expired session.')), 'session');
  assert.equal(friendlyStatusMessage(403, ''), FORBIDDEN_MESSAGE);
  assert.equal(friendlyStatusMessage(403, 'Not authorized.'), 'Not authorized.');
  assert.equal(friendlyStatusMessage(500, 'Request failed.'), SERVER_ERROR_MESSAGE);
  assert.notEqual(classifyErrorMessage(BAD_RESPONSE_MESSAGE), 'session');
});

test('an offline refresh failure is a retryable lookup error, a rejected refresh token is not', () => {
  assert.equal(isRetryableSessionLookupError({ name: 'AuthRetryableFetchError' }), true);
  assert.equal(isRetryableSessionLookupError({ status: 503 }), true);
  assert.equal(isRetryableSessionLookupError({ message: 'Network request failed' }), true);
  assert.equal(isRetryableSessionLookupError({ name: 'AuthApiError', status: 400, message: 'Invalid Refresh Token' }), false);
  assert.equal(isRetryableSessionLookupError(undefined), false);
});

import assert from 'node:assert/strict';
import test from 'node:test';

import { describeSleeperConnectError, isConnectivityFailure } from './sleeperConnectErrors.ts';

test('user_not_found explains the username and offers the sample', () => {
  const e = describeSleeperConnectError({ status: 'user_not_found', username: 'bob' });
  assert.equal(e.kind, 'user_not_found');
  assert.ok(e.message.includes('"bob"'));
  assert.match(e.hint, /not your display name or email/);
  assert.equal(e.offerSample, true);
  assert.equal(e.offerSleeperSignup, true);
});

test('no_leagues explains seasons and offers the sample', () => {
  const e = describeSleeperConnectError({ status: 'no_leagues', username: 'bob' });
  assert.equal(e.kind, 'no_leagues');
  assert.match(e.hint, /this season and last season/);
  assert.equal(e.offerSample, true);
});

test('unavailable and network are a retry message', () => {
  assert.equal(describeSleeperConnectError({ status: 'unavailable' }).kind, 'network');
  assert.match(describeSleeperConnectError({ status: 'network' }).hint, /try again/);
});

test('unknown status falls back to the server message', () => {
  assert.equal(describeSleeperConnectError({ status: 'x', serverMessage: 'Boom' }).message, 'Boom');
});

test('isConnectivityFailure', () => {
  assert.equal(isConnectivityFailure({ status: 0 }), true);
  assert.equal(isConnectivityFailure({ status: 503 }), true);
  assert.equal(isConnectivityFailure(new TypeError('Network request failed')), true);
  assert.equal(isConnectivityFailure({ status: 400 }), false);
});

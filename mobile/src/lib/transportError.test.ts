// Run with: node --experimental-strip-types --test src/lib/transportError.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { isTransportError, isTransportErrorMessage } from './transportError.ts';

test('isTransportError: recognizes a real RN fetch network-transport TypeError', () => {
  assert.equal(isTransportError(new TypeError('Network request failed')), true);
  assert.equal(isTransportError(new TypeError('Failed to fetch')), true);
  assert.equal(isTransportError(new TypeError('Load failed')), true);
  assert.equal(isTransportError(new TypeError('The network connection was lost.')), true);
  assert.equal(
    isTransportError(new TypeError('A server with the specified hostname could not be found.')),
    true,
  );
  assert.equal(isTransportError(new TypeError('The internet connection appears to be offline.')), true);
});

test('isTransportError: recognizes the short-form signatures the spec calls out', () => {
  assert.equal(isTransportError(new Error('network connection lost')), true);
  assert.equal(isTransportError(new Error('hostname could not be found')), true);
  assert.equal(isTransportError(new Error('connection offline')), true);
});

test('isTransportError: does NOT classify an ordinary programming TypeError as a network failure', () => {
  const err = new TypeError("Cannot read properties of undefined (reading 'is_premium')");
  assert.equal(isTransportError(err), false);
});

test('isTransportError: does NOT classify an unrelated Error as a network failure', () => {
  assert.equal(isTransportError(new Error('some other error')), false);
  assert.equal(isTransportError(new RangeError('Invalid array length')), false);
});

test('isTransportError: recognizes AbortError/TimeoutError regardless of message', () => {
  const abort = new Error('this was aborted');
  abort.name = 'AbortError';
  assert.equal(isTransportError(abort), true);

  const timeout = new Error('ran too long');
  timeout.name = 'TimeoutError';
  assert.equal(isTransportError(timeout), true);
});

test('isTransportError: false for non-Error values', () => {
  assert.equal(isTransportError({ status: 500 }), false);
  assert.equal(isTransportError(null), false);
  assert.equal(isTransportError(undefined), false);
  assert.equal(isTransportError('Network request failed'), false);
});

test('isTransportErrorMessage: plain message matcher used by both errorMessages.ts and backgroundRetry.ts', () => {
  assert.equal(isTransportErrorMessage('Network request failed'), true);
  assert.equal(isTransportErrorMessage("Cannot read properties of undefined (reading 'is_premium')"), false);
});

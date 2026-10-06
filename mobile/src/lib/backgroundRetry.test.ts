// Run with: node --experimental-strip-types --test src/lib/backgroundRetry.test.ts
// (mobile has no jest/test runner configured yet — see this PR's description
// for why plain Node's built-in test runner was used instead of adding one.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { isTransientNetworkError, withBackgroundRetry } from './backgroundRetry.ts';

test('isTransientNetworkError: true only for a bare TypeError (RN fetch transport failure)', () => {
  assert.equal(isTransientNetworkError(new TypeError('Network request failed')), true);
  assert.equal(isTransientNetworkError(new Error('some other error')), false);
  assert.equal(isTransientNetworkError({ status: 500 }), false);
  assert.equal(isTransientNetworkError(null), false);
});

test('withBackgroundRetry: succeeds on the first try without retrying', async () => {
  let calls = 0;
  const result = await withBackgroundRetry(
    async () => {
      calls += 1;
      return 'ok';
    },
    () => true,
  );
  assert.equal(result, 'ok');
  assert.equal(calls, 1);
});

test('withBackgroundRetry: retries once and succeeds when a transient error follows a background transition', async () => {
  let calls = 0;
  const result = await withBackgroundRetry(
    async () => {
      calls += 1;
      if (calls === 1) throw new TypeError('Network request failed');
      return 'ok-after-retry';
    },
    () => true, // app was backgrounded during the attempt
  );
  assert.equal(result, 'ok-after-retry');
  assert.equal(calls, 2);
});

test('withBackgroundRetry: does NOT retry a transient error if the app was never backgrounded', async () => {
  let calls = 0;
  await assert.rejects(
    withBackgroundRetry(
      async () => {
        calls += 1;
        throw new TypeError('Network request failed');
      },
      () => false, // no background transition — a real connectivity problem
    ),
    TypeError,
  );
  assert.equal(calls, 1);
});

test('withBackgroundRetry: never retries a real HTTP/ApiError even if backgrounded', async () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  let calls = 0;
  await assert.rejects(
    withBackgroundRetry(
      async () => {
        calls += 1;
        throw new ApiError(404, 'Not found');
      },
      () => true,
    ),
    ApiError,
  );
  assert.equal(calls, 1);
});

test('withBackgroundRetry: gives up after a single retry (no infinite loop / backoff)', async () => {
  let calls = 0;
  await assert.rejects(
    withBackgroundRetry(
      async () => {
        calls += 1;
        throw new TypeError('Network request failed');
      },
      () => true,
    ),
    TypeError,
  );
  assert.equal(calls, 2);
});

test('isTransientNetworkError: false for an ordinary programming TypeError (not just any TypeError)', () => {
  assert.equal(
    isTransientNetworkError(new TypeError("Cannot read properties of undefined (reading 'is_premium')")),
    false,
  );
});

test('withBackgroundRetry: does NOT retry an arbitrary programming TypeError even if backgrounded', async () => {
  let calls = 0;
  await assert.rejects(
    withBackgroundRetry(
      async () => {
        calls += 1;
        throw new TypeError("Cannot read properties of undefined (reading 'is_premium')");
      },
      () => true, // backgrounded — but this still isn't a transport failure
    ),
    TypeError,
  );
  assert.equal(calls, 1);
});

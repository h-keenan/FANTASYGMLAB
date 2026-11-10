// Run with: node --experimental-strip-types --test src/lib/busyRetry.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { MAX_BUSY_RETRIES, MAX_BUSY_WAIT_MS, busyDelayMs, isServerBusyError, parseRetryAfterSeconds, withServerBusyRetry } from './busyRetry.ts';

const busy = (retryAfterSeconds?: number) => ({ status: 503, code: 'server_busy', retryAfterSeconds });

test('isServerBusyError: only 503 server_busy', () => {
  assert.equal(isServerBusyError(busy(3)), true);
  assert.equal(isServerBusyError({ status: 503 }), false);
  assert.equal(isServerBusyError({ status: 429, code: 'server_busy' }), false);
  assert.equal(isServerBusyError(null), false);
});

test('parseRetryAfterSeconds', () => {
  assert.equal(parseRetryAfterSeconds('5'), 5);
  assert.equal(parseRetryAfterSeconds('2.2'), 3);
  assert.equal(parseRetryAfterSeconds(''), undefined);
  assert.equal(parseRetryAfterSeconds('Wed, 21 Oct 2026 07:28:00 GMT'), undefined);
});

test('busyDelayMs honors hint, jitters up, caps', () => {
  assert.equal(busyDelayMs(4, 0, () => 0), 4000);
  assert.equal(busyDelayMs(4, 0, () => 1), 4800);
  assert.equal(busyDelayMs(undefined, 1, () => 0), 4000);
  assert.equal(busyDelayMs(60, 0, () => 0), MAX_BUSY_WAIT_MS);
});

test('retries a busy GET then succeeds', async () => {
  let calls = 0;
  const waits: number[] = [];
  const result = await withServerBusyRetry(
    async () => {
      calls += 1;
      if (calls === 1) throw busy(2);
      return 'ok';
    },
    { canRetry: true, sleep: async (ms) => void waits.push(ms), random: () => 0 },
  );
  assert.equal(result, 'ok');
  assert.equal(calls, 2);
  assert.deepEqual(waits, [2000]);
});

test('gives up after the retry budget', async () => {
  let calls = 0;
  const err = busy(1);
  await assert.rejects(
    withServerBusyRetry(async () => { calls += 1; throw err; }, { canRetry: true, sleep: async () => {} }),
    (e) => e === err,
  );
  assert.equal(calls, MAX_BUSY_RETRIES + 1);
});

test('never retries writes or non-busy errors', async () => {
  let calls = 0;
  await assert.rejects(withServerBusyRetry(async () => { calls += 1; throw busy(1); }, { canRetry: false }));
  await assert.rejects(withServerBusyRetry(async () => { calls += 1; throw { status: 500 }; }, { canRetry: true }));
  assert.equal(calls, 2);
});

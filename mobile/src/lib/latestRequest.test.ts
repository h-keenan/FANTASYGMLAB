import assert from 'node:assert/strict';
import test from 'node:test';

import { createLatestGate, createSingleFlight } from './latestRequest.ts';

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

test('latest gate ignores league A answer when B was requested later and answered first', async () => {
  const gate = createLatestGate(true);
  let shown = '';
  const a = deferred<string>();
  const b = deferred<string>();
  const load = (d: { promise: Promise<string> }) => {
    const current = gate.begin();
    return d.promise.then((v) => {
      if (current()) shown = v;
    });
  };
  const pa = load(a);
  const pb = load(b);
  b.resolve('B');
  await pb;
  a.resolve('A');
  await pa;
  assert.equal(shown, 'B');
});

test('latest gate cancel retires tickets; kill switch keeps them current', () => {
  const gate = createLatestGate(true);
  const t = gate.begin();
  gate.cancel();
  assert.equal(t(), false);
  const off = createLatestGate(false);
  const first = off.begin();
  off.begin();
  assert.equal(first(), true);
});

test('single flight drops a tap while pending, clears on settle and on reject', async () => {
  const guard = createSingleFlight(true);
  const d = deferred<number>();
  let calls = 0;
  const first = guard.run(() => (calls++, d.promise));
  assert.equal(guard.pending, true);
  assert.equal(guard.run(() => (calls++, Promise.resolve(2))), undefined);
  d.resolve(1);
  await first;
  assert.equal(guard.pending, false);
  await assert.rejects(guard.run(() => Promise.reject(new Error('x')))!, /x/);
  assert.equal(guard.pending, false);
  assert.equal(calls, 1);
});

test('single flight kill switch lets every call through', () => {
  const guard = createSingleFlight(false);
  guard.run(() => deferred<number>().promise);
  assert.notEqual(guard.run(() => Promise.resolve(1)), undefined);
});

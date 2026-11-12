// Run with: node --experimental-strip-types --test src/lib/lazyModule.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { createLazyLoader, preloadInSequence } from './lazyModule.ts';

test('loads once, on first use, and returns the same value', () => {
  let calls = 0;
  const loader = createLazyLoader(() => ({ id: ++calls }));
  assert.equal(calls, 0);
  assert.equal(loader.isLoaded(), false);
  const a = loader.get();
  const b = loader.get();
  assert.equal(calls, 1);
  assert.equal(a, b);
  assert.equal(loader.isLoaded(), true);
});

test('a loader that throws is not marked loaded and can be retried', () => {
  let fail = true;
  const loader = createLazyLoader(() => {
    if (fail) throw new Error('boom');
    return 'ok';
  });
  assert.throws(() => loader.get(), /boom/);
  assert.equal(loader.isLoaded(), false);
  fail = false;
  assert.equal(loader.get(), 'ok');
});

test('preload runs one loader per scheduled turn, skipping loaded ones', () => {
  const order: string[] = [];
  const mk = (name: string) => createLazyLoader(() => order.push(name));
  const a = mk('a');
  const b = mk('b');
  const c = mk('c');
  b.get();
  order.length = 0;
  const turns: Array<() => void> = [];
  preloadInSequence([a, b, c], (run) => turns.push(run));
  assert.equal(turns.length, 1);
  assert.deepEqual(order, []);
  turns.shift()!();
  assert.deepEqual(order, ['a']);
  turns.shift()!();
  assert.deepEqual(order, ['a', 'c']);
  assert.equal(turns.length, 0);
});

test('a failing preload is reported and does not stop the rest', () => {
  const errors: unknown[] = [];
  const bad = createLazyLoader((): number => {
    throw new Error('bad');
  });
  let ran = false;
  const good = createLazyLoader(() => {
    ran = true;
  });
  const turns: Array<() => void> = [];
  preloadInSequence([bad, good], (run) => turns.push(run), (e) => errors.push(e));
  while (turns.length) turns.shift()!();
  assert.equal(errors.length, 1);
  assert.equal(ran, true);
});

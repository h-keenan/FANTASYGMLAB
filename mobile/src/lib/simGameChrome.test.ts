// Run with: node --experimental-strip-types --test src/lib/simGameChrome.test.ts
import assert from 'node:assert/strict';
import { test } from 'node:test';

// react is only needed for the hook; the store itself is pure.
const { simGameChrome } = await import('./simGameChrome.ts');

test('store notifies subscribers only on change and unsubscribes', () => {
  let calls = 0;
  const off = simGameChrome.subscribe(() => {
    calls += 1;
  });
  assert.equal(simGameChrome.get(), false);
  simGameChrome.set(true);
  simGameChrome.set(true);
  assert.equal(simGameChrome.get(), true);
  assert.equal(calls, 1);
  off();
  simGameChrome.set(false);
  assert.equal(calls, 1);
  assert.equal(simGameChrome.get(), false);
});

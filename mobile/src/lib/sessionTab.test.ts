// Run with: node --experimental-strip-types --test src/lib/sessionTab.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { createMemoryTabStore, readSavedTab, resolveTab, saveTab, tabDirection } from './sessionTab.ts';

test('resolves remembered, then initial, then first', () => {
  assert.equal(resolveTab('stats', ['a', 'stats'], 'a'), 'stats');
  assert.equal(resolveTab('gone', ['a', 'b'], 'b'), 'b');
  assert.equal(resolveTab(null, ['a', 'b'], 'zzz'), 'a');
  assert.equal(resolveTab(null, [], undefined), '');
});

test('slides toward the picked tab', () => {
  assert.equal(tabDirection(['a', 'b', 'c'], 'a', 'c'), 1);
  assert.equal(tabDirection(['a', 'b', 'c'], 'c', 'b'), -1);
  assert.equal(tabDirection(['a', 'b'], 'a', 'a'), 0);
});

test('round-trips through a store and shrugs off a throwing one', () => {
  const store = createMemoryTabStore();
  saveTab(store, 'pqv', 'history');
  assert.equal(readSavedTab(store, 'pqv'), 'history');
  assert.equal(readSavedTab(store, 'other'), null);
  const bad = { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); } };
  assert.equal(readSavedTab(bad, 'pqv'), null);
  assert.doesNotThrow(() => saveTab(bad, 'pqv', 'a'));
});

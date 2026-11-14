// Run with: node --experimental-strip-types --test src/lib/sheetTabs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { managerProfileTabs, nextPanelMinHeight, percentileTabs } from './sheetTabs.ts';

test('manager profile always has Overview and drops empty tabs', () => {
  assert.deepEqual(managerProfileTabs({ hasProfile: false, tendencyCount: 0, tradeCount: 0 }).map((t) => t.key), ['overview']);
  assert.deepEqual(managerProfileTabs({ hasProfile: true, tendencyCount: 4, tradeCount: 2 }).map((t) => t.label), ['Overview', 'Tendencies', 'Trades']);
});

test('percentile tabs follow what is loaded', () => {
  assert.deepEqual(percentileTabs({ hasFullPool: false, mineCount: 0 }), []);
  assert.deepEqual(percentileTabs({ hasFullPool: true, mineCount: 2 }).map((t) => t.key), ['bucket', 'find', 'mine']);
});

test('panel min height only grows', () => {
  assert.equal(nextPanelMinHeight(0, 120.2), 121);
  assert.equal(nextPanelMinHeight(300, 120), 300);
  assert.equal(nextPanelMinHeight(300, NaN), 300);
});

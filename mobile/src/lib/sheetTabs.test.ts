// Run with: node --experimental-strip-types --test src/lib/sheetTabs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { chromeDock, managerProfileTabs, nextPanelMinHeight, percentileTabs, stickyTabsOffset } from './sheetTabs.ts';

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

test('sticky strip docks flush under chrome', () => {
  assert.deepEqual(stickyTabsOffset(24, 40), { top: 16, mask: 40 });
  assert.equal(chromeDock(52, 44), 12);
});

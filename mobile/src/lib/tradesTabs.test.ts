import test from 'node:test';
import assert from 'node:assert/strict';

import { ORB_TABS } from './orbTabs.ts';
import { TRADES_TAB_OPTIONS } from './tradesTabs.ts';

test('Trades screen tab labels match the GM orb Trades search labels, in order', () => {
  const orbTabs = ORB_TABS.Trades.filter((tab) => tab.params?.initialTab);
  assert.deepEqual(
    TRADES_TAB_OPTIONS.map((tab) => tab.label),
    orbTabs.map((tab) => tab.label),
  );
});

test('each Trades tab opens the same initialTab key the orb search passes', () => {
  for (const option of TRADES_TAB_OPTIONS) {
    const orb = ORB_TABS.Trades.find((tab) => tab.label === option.label);
    assert.equal(orb?.params?.initialTab, option.key);
  }
});

test('the web wording is Hub / Finder / Analyzer', () => {
  assert.deepEqual(
    TRADES_TAB_OPTIONS.map((tab) => tab.label),
    ['Hub', 'Finder', 'Analyzer'],
  );
});

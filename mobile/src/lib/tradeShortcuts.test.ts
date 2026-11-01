// Run with: node --experimental-strip-types --test src/lib/tradeShortcuts.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { isTradeAnalyzerRoute, quickAddPlacement, rosterOwnershipFrom, tradeShortcutsFor } from './tradeShortcuts.ts';

const ownership = rosterOwnershipFrom({ players: ['1', 2] }, [
  { roster_id: 1, players: ['1', '2'] },
  { roster_id: 2, players: ['3', '4'] },
  { roster_id: 3, players: null },
]);

test('rosterOwnershipFrom collects my ids and every rostered id as strings', () => {
  assert.deepEqual([...ownership.myPlayerIds].sort(), ['1', '2']);
  assert.deepEqual([...ownership.rosteredPlayerIds].sort(), ['1', '2', '3', '4']);
});

test('tradeShortcutsFor: own player gets both actions', () => {
  assert.deepEqual(tradeShortcutsFor('1', ownership), { canAddToTrade: true, canFindTrades: true });
});

test("tradeShortcutsFor: another team's player gets Add to Trade only", () => {
  assert.deepEqual(tradeShortcutsFor('3', ownership), { canAddToTrade: true, canFindTrades: false });
});

test('tradeShortcutsFor: free agent, missing id or unknown ownership gets neither', () => {
  const none = { canAddToTrade: false, canFindTrades: false };
  assert.deepEqual(tradeShortcutsFor('99', ownership), none);
  assert.deepEqual(tradeShortcutsFor('', ownership), none);
  assert.deepEqual(tradeShortcutsFor(null, ownership), none);
  assert.deepEqual(tradeShortcutsFor('1', null), none);
});

const teams = [
  { rosterId: '2', playerIds: new Set(['3', '4']) },
  { rosterId: '3', playerIds: new Set(['5']) },
];

test('quickAddPlacement: own player goes to send and focuses receive', () => {
  assert.deepEqual(quickAddPlacement('1', ownership.myPlayerIds, teams), {
    side: 'send',
    partnerRosterId: null,
    focusSide: 'receive',
  });
});

test("quickAddPlacement: another team's player goes to receive, selects the owner, focuses send", () => {
  assert.deepEqual(quickAddPlacement('5', ownership.myPlayerIds, teams), {
    side: 'receive',
    partnerRosterId: '3',
    focusSide: 'send',
  });
});

test('quickAddPlacement: unrostered or empty id fails open', () => {
  assert.equal(quickAddPlacement('99', ownership.myPlayerIds, teams), null);
  assert.equal(quickAddPlacement('', ownership.myPlayerIds, teams), null);
});

test('isTradeAnalyzerRoute: only the Analyzer tab of the Trades host', () => {
  assert.equal(isTradeAnalyzerRoute('Trades', 'make'), true);
  assert.equal(isTradeAnalyzerRoute('Trades', undefined), true);
  assert.equal(isTradeAnalyzerRoute('Trades', 'search'), false);
  assert.equal(isTradeAnalyzerRoute('Waivers', 'make'), false);
  assert.equal(isTradeAnalyzerRoute(undefined), false);
});

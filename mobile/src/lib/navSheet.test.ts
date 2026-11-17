// Run with: node --experimental-strip-types --test src/lib/navSheet.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { navSheetGroups, navSheetNoMatch, navSheetSearchCopy } from './navSheet.ts';

const rows = (...n: string[]) => n.map((label) => ({ label }));

test('groups: league name, GM Tools, General, Account inside a league', () => {
  const g = navSheetGroups({ leagueName: 'Revivalry', core: rows('Today'), tools: rows('Trade Hub'), general: rows('News'), account: rows('Account') });
  assert.deepEqual(g.map((x) => [x.id, x.title]), [['league', 'Revivalry'], ['tools', 'GM Tools'], ['general', 'General'], ['account', 'Account']]);
});

test('groups: no league groups outside a league; empty groups dropped', () => {
  const g = navSheetGroups({ leagueName: null, core: rows('Today'), tools: rows('Trade Hub'), general: rows('News'), account: [] });
  assert.deepEqual(g.map((x) => x.id), ['general']);
});

test('search copy mentions players only with a league', () => {
  assert.match(navSheetSearchCopy(true).label, /players/);
  assert.doesNotMatch(navSheetSearchCopy(false).label, /players/);
  assert.ok(navSheetNoMatch(false, ' zz ').includes('“zz”'));
});

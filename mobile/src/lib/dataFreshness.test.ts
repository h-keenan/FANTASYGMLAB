// Run with: node --experimental-strip-types --test src/lib/dataFreshness.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { freshnessAsOf, freshnessLabel, freshnessText, leagueStaleLabel } from './dataFreshness.ts';

const NOW = new Date(2026, 10, 19, 12, 0, 0).getTime();
const secs = (d: Date) => d.getTime() / 1000;

test('values say how long ago', () => {
  assert.equal(freshnessText('values', secs(new Date(2026, 10, 19, 10, 0)), NOW), 'Values as of 2h ago');
  assert.equal(freshnessText('values', secs(new Date(2026, 10, 19, 11, 40)), NOW), 'Values as of 20m ago');
});

test('injuries and prospects use the clock or date', () => {
  assert.equal(freshnessText('injuries', secs(new Date(2026, 10, 19, 9, 40)), NOW), 'Injuries updated 9:40am');
  assert.equal(freshnessText('prospects', secs(new Date(2026, 10, 12, 9, 0)), NOW), 'Prospects updated Nov 12');
});

test('over the threshold adds a plain may-be-behind note', () => {
  assert.equal(freshnessText('values', secs(new Date(2026, 10, 17, 12, 0)), NOW), 'Values as of 2d ago (may be behind)');
});

test('no honest timestamp means no label; a checkout mtime is never trusted for values', () => {
  const mtime = { datasets: [{ name: 'values_fantasycalc', as_of: secs(new Date(2026, 10, 19, 11, 55)), as_of_source: 'file_mtime' }] };
  assert.equal(freshnessAsOf(mtime, 'values'), null);
  assert.equal(freshnessLabel(null, 'injuries', NOW), null);
  const ok = { datasets: [{ name: 'values_fantasycalc', as_of: secs(new Date(2026, 10, 19, 10, 0)), as_of_source: 'fetch_timestamp' }] };
  assert.equal(freshnessLabel(ok, 'values', NOW), 'Values as of 2h ago');
});

test('leagueStaleLabel says how old last-known league data is, flagged as possibly behind', () => {
  assert.equal(leagueStaleLabel(new Date(2026, 10, 19, 11, 48).toISOString(), NOW), 'League data as of 12m ago (may be behind)');
  assert.equal(leagueStaleLabel(new Date(2026, 10, 19, 9, 0).toISOString(), NOW), 'League data as of 3h ago (may be behind)');
});

test('leagueStaleLabel says nothing for live data or an unreadable stamp', () => {
  assert.equal(leagueStaleLabel(undefined, NOW), null);
  assert.equal(leagueStaleLabel('', NOW), null);
  assert.equal(leagueStaleLabel('not a date', NOW), null);
});

// Run with: node --experimental-strip-types --test src/lib/leagueSwitch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { leagueSwitchDestination } from './leagueSwitch.ts';

const target = { leagueId: 'NEW', leagueName: 'New League' };

test('a league-scoped screen keeps the screen with the new league', () => {
  assert.deepEqual(
    leagueSwitchDestination({ name: 'Waivers', params: { leagueId: 'OLD', leagueName: 'Old' } }, 'OLD', target),
    { name: 'Waivers', params: { leagueId: 'NEW', leagueName: 'New League' } },
  );
});

test('league-independent extras are kept, old-league extras are dropped', () => {
  assert.deepEqual(
    leagueSwitchDestination(
      { name: 'Trades', params: { leagueId: 'OLD', leagueName: 'Old', initialTab: 'search', tradePlayer: { player_id: '1' } } },
      'OLD',
      target,
    ),
    { name: 'Trades', params: { leagueId: 'NEW', leagueName: 'New League', initialTab: 'search' } },
  );
  assert.deepEqual(
    leagueSwitchDestination({ name: 'Teams', params: { leagueId: 'OLD', leagueName: 'Old', metric: 'age' } }, 'OLD', target),
    { name: 'Teams', params: { leagueId: 'NEW', leagueName: 'New League', metric: 'age' } },
  );
});

test('screens with old-league params, or not league-scoped, go to Dashboard', () => {
  const home = { name: 'Dashboard', params: { leagueId: 'NEW', leagueName: 'New League' } };
  assert.deepEqual(
    leagueSwitchDestination({ name: 'PickDetail', params: { leagueId: 'OLD', leagueName: 'Old', pick: {} } }, 'OLD', target),
    home,
  );
  assert.deepEqual(leagueSwitchDestination({ name: 'Portfolio' }, 'OLD', target), home);
  assert.deepEqual(leagueSwitchDestination(null, 'OLD', target), home);
  // Current route shows a different league than the one being switched from.
  assert.deepEqual(
    leagueSwitchDestination({ name: 'Waivers', params: { leagueId: 'OTHER', leagueName: 'x' } }, 'OLD', target),
    home,
  );
});

test('ESPN target: unsupported screens fall back to My Team, Trades opens on Make a Trade', () => {
  const espn = { leagueId: 'espn:1:2026', leagueName: 'ESPN' };
  assert.deepEqual(
    leagueSwitchDestination({ name: 'Waivers', params: { leagueId: 'OLD', leagueName: 'Old' } }, 'OLD', espn),
    { name: 'MyTeam', params: espn },
  );
  assert.deepEqual(
    leagueSwitchDestination({ name: 'Trades', params: { leagueId: 'OLD', leagueName: 'Old', initialTab: 'block' } }, 'OLD', espn),
    { name: 'Trades', params: { ...espn, initialTab: 'make' } },
  );
});

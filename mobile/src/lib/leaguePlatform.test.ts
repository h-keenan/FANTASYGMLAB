import assert from 'node:assert/strict';
import { test } from 'node:test';

import { espnRouteSupported, isEspnLeagueId, leagueHomeRoute } from './leaguePlatform.ts';
import { glanceEspnNote, glanceFailedNote } from './leaguesGlance.ts';

test('recognises ESPN league ids by their prefix', () => {
  assert.equal(isEspnLeagueId('espn:42654852:2026'), true);
  assert.equal(isEspnLeagueId('1180112345678901234'), false);
  assert.equal(isEspnLeagueId(undefined), false);
});

test('ESPN leagues open My Team, Sleeper leagues open Dashboard', () => {
  assert.equal(leagueHomeRoute('espn:42654852:2026'), 'MyTeam');
  assert.equal(leagueHomeRoute('1180112345678901234'), 'Dashboard');
});

test('only the screens ESPN can feed are supported', () => {
  for (const route of ['MyTeam', 'Trades', 'Players', 'PlayerDetail', 'Teams']) {
    assert.equal(espnRouteSupported(route), true, route);
  }
  for (const route of ['Dashboard', 'Waivers', 'Matchup', 'Alerts', 'GmPlan', 'DraftCenter', 'LeagueDetail']) {
    assert.equal(espnRouteSupported(route), false, route);
  }
});

test('ESPN leagues get their own glance note, not the "Couldn\'t load" one', () => {
  const failed = [
    { league_id: 'espn:1:2026', league_name: 'ESPN Dynasty', reason: 'espn_not_supported' },
    { league_id: '99', league_name: 'Broken', reason: 'unavailable' },
  ];
  assert.equal(glanceFailedNote(failed), "Couldn't load 1 league right now: Broken.");
  assert.equal(glanceEspnNote(failed), 'Not available for ESPN leagues yet: ESPN Dynasty. Open it from My Team.');
  assert.equal(glanceEspnNote([failed[1]]), '');
});

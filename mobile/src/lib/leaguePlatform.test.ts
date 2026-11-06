import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ESPN_COOKIE_STEPS, ESPN_LOGIN_WHY, espnCredentialFailureMessage, espnRouteSupported, importedPlatformLabel, isEspnLeagueId, leagueHomeRoute, notAvailableMessage } from './leaguePlatform.ts';
import { glanceEspnNote, glanceFailedNote } from './leaguesGlance.ts';

test('recognises ESPN league ids by their prefix', () => {
  assert.equal(isEspnLeagueId('espn:42654852:2026'), true);
  assert.equal(isEspnLeagueId('1180112345678901234'), false);
  assert.equal(isEspnLeagueId(undefined), false);
});

test('Fleaflicker and MFL leagues are imported leagues with their own label', () => {
  assert.equal(isEspnLeagueId('fleaflicker:206154:2025'), true);
  assert.equal(isEspnLeagueId('mfl:10015:2025'), true);
  assert.equal(isEspnLeagueId('yahoo:1:2025'), false);
  assert.equal(importedPlatformLabel('mfl:10015:2025'), 'MFL');
  assert.equal(notAvailableMessage('fleaflicker:206154:2025'), 'Not available for Fleaflicker leagues yet.');
  assert.equal(notAvailableMessage('espn:1:2026'), 'Not available for ESPN leagues yet.');
  assert.equal(leagueHomeRoute('mfl:10015:2025'), 'Dashboard');
});

test('every league opens on its Dashboard', () => {
  assert.equal(leagueHomeRoute('espn:42654852:2026'), 'Dashboard');
  assert.equal(leagueHomeRoute('1180112345678901234'), 'Dashboard');
});

test('only the screens ESPN can feed are supported', () => {
  for (const route of ['Dashboard', 'Matchup', 'MyTeam', 'Trades', 'Players', 'PlayerDetail', 'Teams']) {
    assert.equal(espnRouteSupported(route), true, route);
  }
  for (const route of ['Waivers', 'Alerts', 'GmPlan', 'DraftCenter', 'LeagueDetail']) {
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

test('ESPN login copy explains both cookies and prefers the server message', () => {
  assert.match(ESPN_COOKIE_STEPS.join(' '), /espn_s2/);
  assert.match(ESPN_COOKIE_STEPS.join(' '), /SWID/);
  assert.match(ESPN_LOGIN_WHY, /encrypted/);
  assert.equal(espnCredentialFailureMessage({ reason: 'x', message: 'Server says.' }), 'Server says.');
  assert.match(espnCredentialFailureMessage({ reason: 'not_configured' }), /isn't available yet/);
  assert.match(espnCredentialFailureMessage(null), /Check both values/);
});

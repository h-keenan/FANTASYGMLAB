import assert from 'node:assert/strict';
import test from 'node:test';

import { isLegacyRedirectRoute, normalizeGmPlanTab, resolveLegacyRedirect } from './homeRedirects.ts';

const league = { leagueId: 'L1', leagueName: 'Dynasty One' };

test('League Overview redirects to Dashboard with the league params', () => {
  assert.deepEqual(resolveLegacyRedirect('LeagueDetail', league), { name: 'Dashboard', params: league });
});

test('Watchlist redirects to the GM Plan Watching tab', () => {
  assert.deepEqual(resolveLegacyRedirect('GmTargets', league), {
    name: 'GmPlan',
    params: { ...league, initialTab: 'watching' },
  });
});

test('Team Situation redirects to the GM Plan Overview tab', () => {
  assert.deepEqual(resolveLegacyRedirect('TeamStance', league), {
    name: 'GmPlan',
    params: { ...league, initialTab: 'overview' },
  });
});

test('Playoff Odds redirects to the League Rankings Playoff Odds tab', () => {
  assert.deepEqual(resolveLegacyRedirect('PlayoffOdds', league), {
    name: 'Teams',
    params: { ...league, initialTab: 'playoff' },
  });
});

test('real routes are not redirected', () => {
  assert.equal(resolveLegacyRedirect('Dashboard', league), null);
  assert.equal(resolveLegacyRedirect('GmPlan', league), null);
  assert.equal(resolveLegacyRedirect('toString', league), null);
  assert.equal(isLegacyRedirectRoute('Dashboard'), false);
  assert.equal(isLegacyRedirectRoute('LeagueDetail'), true);
  assert.equal(isLegacyRedirectRoute(undefined), false);
});

test('GM Plan tab param is validated', () => {
  assert.equal(normalizeGmPlanTab('watching'), 'watching');
  assert.equal(normalizeGmPlanTab('core'), 'core');
  assert.equal(normalizeGmPlanTab('nonsense'), 'overview');
  assert.equal(normalizeGmPlanTab(undefined), 'overview');
});

test('2026-11-16 consolidation: retired pages redirect to their new tab or section', () => {
  assert.deepEqual(resolveLegacyRedirect('Alerts', league), { name: 'Dashboard', params: { ...league, focus: 'alerts' } });
  assert.deepEqual(resolveLegacyRedirect('LiveDraft', league), { name: 'DraftCenter', params: { ...league, tab: 'live' } });
  assert.deepEqual(resolveLegacyRedirect('Portfolio', league), { name: 'Home', params: { focus: 'standing' } });
  assert.deepEqual(resolveLegacyRedirect('Recap', { ...league, initialTab: 'roundup', week: 9 }), {
    name: 'News',
    params: { ...league, week: 9, initialTab: 'league', recapsTab: 'roundup' },
  });
  assert.deepEqual(resolveLegacyRedirect('Recap', league), { name: 'News', params: { ...league, initialTab: 'league' } });
});

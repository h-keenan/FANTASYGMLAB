import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { armTrialOffer, firstRunStage, shouldShowTrialOffer, type FirstRunStage } from './firstRunFlow.ts';
import { planOf } from './plan.ts';
import { SAMPLE_DASHBOARD_ITEMS, SAMPLE_ROSTER, SAMPLE_ROUTE, SAMPLE_TABS, SAMPLE_TRY_LABEL } from './sampleLeague.ts';

// The app has no headless render path (React Native, no react-native-web / jest in mobile/), so this is the mobile half of the web
// "new-user-smoke" (scripts/sim_layout_playwright/new_user_smoke.mjs): the whole first-run journey walked through the same pure state machine the
// RootNavigator / Home screen read, plus source checks that the screens are still wired to it. Run by `npm test` in the mobile-app CI job.
const read = (p: string): string => readFileSync(p, { encoding: 'utf8' });

test('new user journey: sign in -> intro -> connect -> Today, in order, with the sample league reachable at every step', () => {
  const journey: FirstRunStage[] = [];
  // Signed out.
  journey.push(firstRunStage({ signedIn: false, introSeen: false, leagueCount: null }));
  // Signed in with a fresh account: intro first, then (skipped or finished) the connect step.
  journey.push(firstRunStage({ signedIn: true, introSeen: false, leagueCount: null }));
  journey.push(firstRunStage({ signedIn: true, introSeen: true, leagueCount: 0 }));
  // A league saved: its Today.
  journey.push(firstRunStage({ signedIn: true, introSeen: true, leagueCount: 1 }));
  assert.deepEqual(journey, ['sign_in', 'intro', 'connect', 'league_home']);
  // Every stage is billing-blind: the function takes no plan input, so a Free account walks the identical path.
  assert.equal(firstRunStage.length, 1);
  // Two or more leagues reopen the portfolio; a returning user (intro already seen) with leagues never replays the intro.
  assert.equal(firstRunStage({ signedIn: true, introSeen: false, leagueCount: 2 }), 'portfolio');
});

test('free account with no league: lands on the connect step (never a dead end) and the trial offer waits for the first Today', () => {
  assert.equal(firstRunStage({ signedIn: true, introSeen: true, leagueCount: null }), 'connect');
  assert.equal(shouldShowTrialOffer({ state: armTrialOffer('idle'), isPremium: false, onLeagueHome: false }), false);
  assert.equal(shouldShowTrialOffer({ state: armTrialOffer('idle'), isPremium: false, onLeagueHome: true }), true);
  assert.equal(shouldShowTrialOffer({ state: armTrialOffer('idle'), isPremium: true, onLeagueHome: true }), false);
});

test('Pro vs Free through the shared planOf (the same rule web uses)', () => {
  assert.equal(planOf({ entitlement: 'premium', profile_status: 'ok' }), 'pro');
  assert.equal(planOf({ entitlement: 'free', profile_status: 'ok' }), 'free');
  assert.equal(planOf({ entitlement: 'free', profile_status: 'error' }), 'unknown');
  assert.equal(planOf(null), 'unknown');
});

test('sample league has real content for a new user (Today items, roster, tabs) and a labelled entry point', () => {
  assert.ok(SAMPLE_DASHBOARD_ITEMS.length >= 2);
  assert.ok(SAMPLE_ROSTER.length >= 5);
  assert.ok(SAMPLE_TABS.some((t) => t.value === 'dashboard'));
  assert.equal(SAMPLE_ROUTE, '/sample-league');
  assert.ok(SAMPLE_TRY_LABEL.length > 0);
});

test('screens stay wired: onboarding intro, Sleeper username connect, sample entry, Today after connect', () => {
  const onboarding = read('src/screens/OnboardingScreen.tsx');
  assert.ok(/skip/i.test(onboarding), 'the intro stays skippable');
  const home = read('src/screens/HomeScreen.tsx');
  assert.ok(/sleeper/i.test(home) && /username/i.test(home), 'Home keeps the Sleeper username connect');
  assert.ok(/SampleLeague/.test(home), 'Home keeps the sample-league entry');
  assert.ok(home.includes("navigation.navigate('Dashboard'"), 'connecting a league opens Today');
  const login = read('src/screens/LoginScreen.tsx');
  assert.ok(/SampleLeague/.test(login), 'the sign-in screen offers the sample league before an account wall');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  FIRST_RUN_FUNNEL_STEPS,
  armTrialOffer,
  dismissTrialOffer,
  firstRunStage,
  funnelStepIndex,
  shouldShowTrialOffer,
} from './firstRunFlow.ts';

// npm test runs from mobile/, so these are cwd-relative.
const read = (p: string): string => readFileSync(p, { encoding: 'utf8' });

test('guard: new account goes intro -> connect -> league home, never a paywall stage', () => {
  assert.equal(firstRunStage({ signedIn: false, introSeen: true, leagueCount: 2 }), 'sign_in');
  assert.equal(firstRunStage({ signedIn: true, introSeen: false, leagueCount: 0 }), 'intro');
  assert.equal(firstRunStage({ signedIn: true, introSeen: true, leagueCount: null }), 'connect');
  assert.equal(firstRunStage({ signedIn: true, introSeen: false, leagueCount: 1 }), 'league_home');
  assert.equal(firstRunStage({ signedIn: true, introSeen: true, leagueCount: 3 }), 'portfolio');
});

test('trial offer: arms once, never re-arms after dismissal, always dismissible', () => {
  assert.equal(armTrialOffer('idle'), 'armed');
  assert.equal(armTrialOffer('dismissed'), 'dismissed');
  assert.equal(dismissTrialOffer(), 'dismissed');
  const base = { state: 'armed' as const, isPremium: false, onLeagueHome: true };
  assert.equal(shouldShowTrialOffer(base), true);
  assert.equal(shouldShowTrialOffer({ ...base, isPremium: true }), false);
  assert.equal(shouldShowTrialOffer({ ...base, onLeagueHome: false }), false);
  assert.equal(shouldShowTrialOffer({ ...base, state: 'dismissed' }), false);
});

test('funnel ids order connect before the first league view', () => {
  assert.deepEqual([...FIRST_RUN_FUNNEL_STEPS], ['level', 'value', 'connect', 'first_league_view']);
  assert.ok(funnelStepIndex('connect') < funnelStepIndex('first_league_view'));
});

test('twin stays byte-identical to web', () => {
  assert.equal(read('src/lib/firstRunFlow.ts'), read('../web-next/src/lib/firstRunFlow.ts'));
});

test('navigation wiring: no screen or guard puts the Paywall in the first-run path', () => {
  // The first-run stack choice depends only on session + onboarding flag.
  const nav = read('src/navigation/RootNavigator.tsx');
  assert.ok(!/useEntitlement|usePremium|is_premium|isPremium|entitlement/i.test(nav.replace(/\/\/.*$/gm, '')));
  // Connecting a league lands on its Dashboard (Today), not the Paywall.
  const home = read('src/screens/HomeScreen.tsx');
  const finishSave = home.slice(home.indexOf('const finishSave'), home.indexOf('const saveLeague = async'));
  assert.ok(!finishSave.includes("'Paywall'"), 'finishSave must not open the Paywall');
  assert.ok(finishSave.includes("navigation.navigate('Dashboard'"));
  // Finishing or skipping the intro never opens the Paywall either.
  assert.ok(!read('src/screens/OnboardingScreen.tsx').includes("navigate('Paywall'"));
  // The offer is a dismissible card on the Dashboard.
  assert.ok(read('src/screens/DashboardScreen.tsx').includes('<FirstValueOfferCard'));
  const card = read('src/components/FirstValueOfferCard.tsx');
  assert.ok(card.includes('TRIAL_OFFER_DISMISS') && card.includes('resolveTrialOffer'));
});

// Run with: node --experimental-strip-types --test src/lib/experienceCopy.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BEGINNER_HELP,
  BEGINNER_LABELS,
  EXPERIENCE_TIERS,
  NEW_FANTASY_HELP,
  experienceCopy,
  levelForTier,
  normalizeExperienceLevel,
  normalizeExperienceTier,
  normalizePrimaryGoal,
  stanceForGoal,
  tierForLevel,
} from './experienceCopy.ts';
import { GLOSSARY, SETTINGS_GLOSSARY_TERMS } from './glossary.ts';

test('beginner gets the plain-language help and labels', () => {
  const copy = experienceCopy('beginner');
  assert.equal(copy.isBeginner, true);
  assert.equal(copy.help('powerRank'), BEGINNER_HELP.powerRank);
  assert.equal(copy.help('playerTier'), BEGINNER_HELP.playerTier);
  assert.equal(copy.label('averageAge', 'Avg Age'), BEGINNER_LABELS.averageAge);
  assert.equal(copy.label('yourFaab', 'Your FAAB'), 'Your Waiver Budget (FAAB)');
});

test('advanced and unset keep today\'s copy exactly', () => {
  for (const level of ['advanced', null] as const) {
    const copy = experienceCopy(level);
    assert.equal(copy.isBeginner, false);
    assert.equal(copy.help('powerRank'), null);
    assert.equal(copy.help('faab'), null);
    assert.equal(copy.label('averageAge', 'Avg Age'), 'Avg Age');
    assert.equal(copy.verdictHelp('ACCEPT'), null);
    assert.equal(copy.impactTagHelp('sell_high'), null);
  }
});

test('verdict and impact-tag lookups map to the right entries', () => {
  const copy = experienceCopy('beginner');
  assert.equal(copy.verdictHelp('ACCEPT'), BEGINNER_HELP.verdictAccept);
  assert.equal(copy.verdictHelp(' counter '), BEGINNER_HELP.verdictCounter);
  assert.equal(copy.verdictHelp('DECLINE'), BEGINNER_HELP.verdictDecline);
  assert.equal(copy.verdictHelp('FAIR'), BEGINNER_HELP.verdictFair);
  assert.equal(copy.verdictHelp('SMASH'), null);
  assert.equal(copy.verdictHelp(undefined), null);
  assert.equal(copy.impactTagHelp('buy_low'), BEGINNER_HELP.impactBuyLow);
  assert.equal(copy.impactTagHelp('sell_high'), BEGINNER_HELP.impactSellHigh);
  assert.equal(copy.impactTagHelp('high_impact'), BEGINNER_HELP.impactHighImpact);
  assert.equal(copy.impactTagHelp(''), null);
});

test('normalizeExperienceLevel only accepts the two real values', () => {
  assert.equal(normalizeExperienceLevel('beginner'), 'beginner');
  assert.equal(normalizeExperienceLevel('advanced'), 'advanced');
  assert.equal(normalizeExperienceLevel('expert'), null);
  assert.equal(normalizeExperienceLevel(null), null);
  assert.equal(normalizeExperienceLevel(undefined), null);
});

test('tiers map to the legacy level and back; unknown values are null', () => {
  assert.equal(levelForTier('new_fantasy'), 'beginner');
  assert.equal(levelForTier('new_dynasty'), 'beginner');
  assert.equal(levelForTier('veteran'), 'advanced');
  assert.equal(tierForLevel('beginner'), 'new_dynasty');
  assert.equal(tierForLevel('advanced'), 'veteran');
  assert.equal(normalizeExperienceTier('veteran'), 'veteran');
  assert.equal(normalizeExperienceTier('expert'), null);
  assert.equal(normalizePrimaryGoal('rebuild'), 'rebuild');
  assert.equal(normalizePrimaryGoal('tank'), null);
});

test('a goal only suggests a Team Situation for win now and rebuild', () => {
  assert.equal(stanceForGoal('win_now'), 'competing');
  assert.equal(stanceForGoal('rebuild'), 'rebuilding');
  assert.equal(stanceForGoal('exploring'), null);
  assert.equal(stanceForGoal(null), null);
});

test('both beginner tiers get captions, new to fantasy gets plainer wording, veteran gets none', () => {
  assert.equal(experienceCopy('beginner', 'new_dynasty').help('powerRank'), BEGINNER_HELP.powerRank);
  assert.equal(experienceCopy('beginner', 'new_fantasy').help('powerRank'), NEW_FANTASY_HELP.powerRank);
  assert.equal(experienceCopy('beginner', 'new_fantasy').help('waiverValue'), BEGINNER_HELP.waiverValue);
  assert.equal(experienceCopy('advanced', 'veteran').help('powerRank'), null);
  assert.equal(experienceCopy('advanced', 'new_fantasy').help('powerRank'), null);
  assert.equal(experienceCopy('beginner', 'new_fantasy').label('averageAge', 'Avg Age'), BEGINNER_LABELS.averageAge);
});

test('onboarding and Settings share one set of tier labels', () => {
  assert.equal(EXPERIENCE_TIERS.new_fantasy.label, 'New to fantasy');
  assert.equal(EXPERIENCE_TIERS.new_dynasty.label, 'New to dynasty');
  assert.equal(EXPERIENCE_TIERS.veteran.label, 'Dynasty veteran');
});

test('the Settings glossary covers PQV, picks, superflex, TEP, FAAB and taxi with real definitions', () => {
  for (const key of ['pqv', 'picks', 'superflex', 'tep', 'faab', 'taxi'] as const) {
    assert.ok(SETTINGS_GLOSSARY_TERMS.includes(key));
    assert.ok(GLOSSARY[key].definition.length > 20);
  }
});

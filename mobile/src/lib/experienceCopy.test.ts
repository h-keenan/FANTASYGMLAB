// Run with: node --experimental-strip-types --test src/lib/experienceCopy.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BEGINNER_HELP,
  BEGINNER_LABELS,
  experienceCopy,
  normalizeExperienceGoal,
  normalizeExperienceLevel,
} from './experienceCopy.ts';

test('beginner gets the plain-language help and labels', () => {
  const copy = experienceCopy('beginner');
  assert.equal(copy.isBeginner, true);
  assert.equal(copy.help('powerRank'), BEGINNER_HELP.powerRank);
  assert.equal(copy.help('playerTier'), BEGINNER_HELP.playerTier);
  assert.equal(copy.label('averageAge', 'Avg Age'), BEGINNER_LABELS.averageAge);
  assert.equal(copy.label('yourFaab', 'Your FAAB'), 'Your Waiver Budget (FAAB)');
});

test('new_to_fantasy gets the exact same beginner copy as beginner', () => {
  const copy = experienceCopy('new_to_fantasy');
  assert.equal(copy.isBeginner, true);
  assert.equal(copy.help('powerRank'), BEGINNER_HELP.powerRank);
  assert.equal(copy.label('averageAge', 'Avg Age'), BEGINNER_LABELS.averageAge);
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

test('normalizeExperienceLevel only accepts the three real values', () => {
  assert.equal(normalizeExperienceLevel('new_to_fantasy'), 'new_to_fantasy');
  assert.equal(normalizeExperienceLevel('beginner'), 'beginner');
  assert.equal(normalizeExperienceLevel('advanced'), 'advanced');
  assert.equal(normalizeExperienceLevel('expert'), null);
  assert.equal(normalizeExperienceLevel(null), null);
  assert.equal(normalizeExperienceLevel(undefined), null);
});

test('normalizeExperienceGoal only accepts the three real values', () => {
  assert.equal(normalizeExperienceGoal('win_now'), 'win_now');
  assert.equal(normalizeExperienceGoal('rebuilding'), 'rebuilding');
  assert.equal(normalizeExperienceGoal('exploring'), 'exploring');
  assert.equal(normalizeExperienceGoal(''), null);
  assert.equal(normalizeExperienceGoal('championship'), null);
  assert.equal(normalizeExperienceGoal(null), null);
  assert.equal(normalizeExperienceGoal(undefined), null);
});

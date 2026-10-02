// Run with: node --experimental-strip-types --test src/lib/formatPlayerName.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  abbreviatePlayerName,
  shouldAbbreviatePlayerName,
  PLAYER_NAME_LENGTH_THRESHOLD,
} from './formatPlayerName.ts';

test('short two-word name shortens to "F. Lastname"', () => {
  assert.equal(abbreviatePlayerName('Jauan Jennings'), 'J. Jennings');
});

test('long name with a multi-word last name keeps the whole last name attached', () => {
  assert.equal(abbreviatePlayerName('Amon-Ra St. Brown'), 'A. St. Brown');
});

test('name with a suffix keeps the suffix attached to the last name, not dropped', () => {
  assert.equal(abbreviatePlayerName('Michael Pittman Jr.'), 'M. Pittman Jr.');
  assert.equal(abbreviatePlayerName('Marvin Harrison Jr.'), 'M. Harrison Jr.');
});

test('hyphenated last name is preserved whole', () => {
  assert.equal(abbreviatePlayerName('Christian Watson-Smith'), 'C. Watson-Smith');
});

test('single-word name (mononym) is returned unchanged — nothing to shrink to an initial', () => {
  assert.equal(abbreviatePlayerName('Neymar'), 'Neymar');
});

test('empty and null/undefined input never crashes and returns an empty string', () => {
  assert.equal(abbreviatePlayerName(''), '');
  assert.equal(abbreviatePlayerName('   '), '');
  assert.equal(abbreviatePlayerName(null), '');
  assert.equal(abbreviatePlayerName(undefined), '');
});

test('extra internal whitespace is normalized', () => {
  assert.equal(abbreviatePlayerName('  Justin   Jefferson  '), 'J. Jefferson');
});

// shouldAbbreviatePlayerName — the deterministic, synchronous "when" that
// replaced onTextLayout-only clip detection (see PlayerNameText.tsx and this
// file's doc comment for how PLAYER_NAME_LENGTH_THRESHOLD was calibrated).

test('a short name stays full — no abbreviation needed', () => {
  assert.equal(shouldAbbreviatePlayerName('Josh Allen'), false);
  assert.equal(shouldAbbreviatePlayerName('Joe Burrow'), false);
  assert.equal(shouldAbbreviatePlayerName('CeeDee Lamb'), false);
});

test('a long name abbreviates immediately and deterministically, no layout callback needed', () => {
  assert.equal(shouldAbbreviatePlayerName('Christian McCaffrey'), true);
  assert.equal(abbreviatePlayerName('Christian McCaffrey'), 'C. McCaffrey');
});

test('names actually observed truncating in production cross the threshold', () => {
  // "Juwan John…" — the exact mid-word clip screenshot evidence showed.
  assert.equal(shouldAbbreviatePlayerName('Juwan Johnson'), true);
  // "Wan'Dale Ro…"
  assert.equal(shouldAbbreviatePlayerName("Wan'Dale Robinson"), true);
  // "Rhamondre Stevenson" — the name from PlayerNameText's own motivating report.
  assert.equal(shouldAbbreviatePlayerName('Rhamondre Stevenson'), true);
});

test('suffixed and hyphenated long names still abbreviate correctly through the threshold path', () => {
  assert.equal(shouldAbbreviatePlayerName('Michael Pittman Jr.'), true);
  assert.equal(abbreviatePlayerName('Michael Pittman Jr.'), 'M. Pittman Jr.');
  assert.equal(shouldAbbreviatePlayerName('Amon-Ra St. Brown'), true);
  assert.equal(abbreviatePlayerName('Amon-Ra St. Brown'), 'A. St. Brown');
});

test('mononyms never need abbreviation even if long, since there is no initial to shrink to', () => {
  assert.equal(shouldAbbreviatePlayerName('Neymar'), false);
  // Even a hypothetical long single-word name degrades gracefully: flagged
  // true by raw length, but abbreviatePlayerName returns it unchanged since
  // there's no "first name" token to shrink — PlayerNameText's numberOfLines
  // backstop is what actually protects layout in that edge case, not this.
  const longMononym = 'Supercalifragilisticexpialidocious';
  assert.equal(shouldAbbreviatePlayerName(longMononym), true);
  assert.equal(abbreviatePlayerName(longMononym), longMononym);
});

test('empty and null/undefined input never needs abbreviation', () => {
  assert.equal(shouldAbbreviatePlayerName(''), false);
  assert.equal(shouldAbbreviatePlayerName('   '), false);
  assert.equal(shouldAbbreviatePlayerName(null), false);
  assert.equal(shouldAbbreviatePlayerName(undefined), false);
});

test('a name exactly at the threshold stays full; one character over abbreviates', () => {
  const atThreshold = 'A'.repeat(PLAYER_NAME_LENGTH_THRESHOLD);
  assert.equal(atThreshold.length, PLAYER_NAME_LENGTH_THRESHOLD);
  assert.equal(shouldAbbreviatePlayerName(atThreshold), false);
  const overThreshold = atThreshold + 'A';
  assert.equal(shouldAbbreviatePlayerName(overThreshold), true);
});

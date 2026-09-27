// Run with: node --experimental-strip-types --test src/lib/formatPlayerName.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { abbreviatePlayerName } from './formatPlayerName.ts';

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

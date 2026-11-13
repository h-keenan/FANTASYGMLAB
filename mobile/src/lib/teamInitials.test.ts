// Run with: node --experimental-strip-types --test src/lib/teamInitials.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { teamInitials } from './teamInitials.ts';

test('first letters of first and last words; two letters for one word', () => {
  assert.equal(teamInitials('Gridiron Goats'), 'GG');
  assert.equal(teamInitials('Blitz'), 'BL');
});

test('never splits an emoji surrogate pair', () => {
  assert.equal(teamInitials('Gridiron Goats 🐐'), 'GG');
  assert.equal(teamInitials('🐐'), '');
});

test('empty and missing names', () => {
  assert.equal(teamInitials(''), '');
  assert.equal(teamInitials(null), '');
});

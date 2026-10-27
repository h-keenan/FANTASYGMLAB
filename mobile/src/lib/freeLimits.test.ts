import test from 'node:test';
import assert from 'node:assert/strict';

import { freeLimitNote } from './freeLimits.ts';
import { GLOSSARY } from './glossary.ts';
import { BEGINNER_HELP } from './experienceCopy.ts';

test('cap note shows used of the server limit', () => {
  const note = freeLimitNote({ kind: 'cap', noun: 'GM Targets', limit: 3, used: 2, isPremium: false });
  assert.equal(note?.text, 'Free: 2 of 3 GM Targets');
  assert.equal(note?.cta, 'upgrade');
});

test('window note uses what is shown, and guests create an account first', () => {
  const note = freeLimitNote({
    kind: 'window',
    noun: 'trade ideas',
    limit: 2,
    total: 7,
    shown: 4,
    isPremium: false,
    isGuest: true,
  });
  assert.equal(note?.text, 'Free: showing 4 of 7 trade ideas');
  assert.equal(note?.ctaLabel, 'Create an account');
});

test('silent for Premium, unknown plan, or no server limit', () => {
  assert.equal(freeLimitNote({ kind: 'cap', noun: 'x', limit: 3, used: 1, isPremium: true }), null);
  assert.equal(freeLimitNote({ kind: 'cap', noun: 'x', limit: 3, used: 1, isPremium: null }), null);
  assert.equal(freeLimitNote({ kind: 'cap', noun: 'x', limit: undefined, used: 1, isPremium: false }), null);
});

test('glossary defines the audited labels and reuses beginner help', () => {
  for (const key of [
    'powerRank',
    'rosterPower',
    'franchiseRank',
    'starterStrength',
    'benchStrength',
    'ovr',
    'pqv',
    'draftPicks',
    'superflex',
    'tep',
  ] as const) {
    assert.ok(GLOSSARY[key].definition.trim().endsWith('.'));
  }
  assert.equal(GLOSSARY.powerRank.definition, BEGINNER_HELP.powerRank);
  assert.equal(GLOSSARY.ovr.definition, BEGINNER_HELP.overallRating);
});

test('glossary covers the P1 onboarding audit gaps: PQV, draft picks, superflex and TEP', () => {
  assert.match(GLOSSARY.pqv.label, /PQV/);
  assert.equal(GLOSSARY.draftPicks.label, 'Draft Picks');
  assert.equal(GLOSSARY.superflex.label, 'Superflex');
  assert.match(GLOSSARY.tep.label, /TEP/);
});

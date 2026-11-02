// Run with: node --experimental-strip-types --test src/lib/playerAvailability.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { availabilityDetailParts, byePillText, cleanInjuryLabel, newsAgeLabel } from './playerAvailability.ts';

test('IR is never rendered as "Ir"', () => {
  assert.equal(cleanInjuryLabel('IR'), 'Injured Reserve');
  assert.equal(cleanInjuryLabel('Questionable'), 'Questionable');
  assert.equal(cleanInjuryLabel('  '), null);
  assert.equal(cleanInjuryLabel(null), null);
});

test('detail parts keep only what the server returned', () => {
  const base = { status: 'IR', label: 'Injured Reserve', severity: 'out', unavailable: true, report: null } as const;
  assert.deepEqual(availabilityDetailParts({ ...base, body_part: 'Knee', return_note: 'No return date reported' }), [
    'Knee',
    'No return date reported',
  ]);
  assert.deepEqual(availabilityDetailParts({ ...base, body_part: null, return_note: 'No return date reported' }), [
    'No return date reported',
  ]);
});

test('bye pill says (this week) only for an unavailable player on bye', () => {
  assert.equal(byePillText(8, true, true), 'Bye: Wk 8 (this week)');
  assert.equal(byePillText(8, true, false), 'Bye: Wk 8');
  assert.equal(byePillText(8, false, true), 'Bye: Wk 8');
});

test('news age label', () => {
  const now = 1_000_000 * 1000;
  assert.equal(newsAgeLabel(1_000_000 - 7200, now), '2h ago');
  assert.equal(newsAgeLabel(null, now), '');
});

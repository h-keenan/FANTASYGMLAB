// Run with: node --experimental-strip-types --test src/lib/injuryDisplay.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { injuryTone } from './injuryDisplay.ts';

test('null/undefined/empty injury_status reads as neutral, never a fabricated "Healthy" success tone', () => {
  // Regression test for the P0 bug: a player with no injury data (e.g. a
  // push-notification deep link, or an unresolved player lookup) must
  // never be shown with the same green tone as a verified-healthy player.
  assert.equal(injuryTone(null), 'neutral');
  assert.equal(injuryTone(undefined), 'neutral');
  assert.equal(injuryTone(''), 'neutral');
});

test('a literal "Healthy" value still reads as success', () => {
  assert.equal(injuryTone('Healthy'), 'success');
});

test('season-ending / out-of-action designations read as danger', () => {
  // 'IR' is Sleeper's real injury_status value for a season-ending injury
  // (confirmed live for the Jaxson Dart P0 incident this guards against).
  assert.equal(injuryTone('Out'), 'danger');
  assert.equal(injuryTone('IR'), 'danger');
  assert.equal(injuryTone('Doubtful'), 'danger');
});

test('day-to-day designations that are neither healthy nor ruled out read as neutral', () => {
  assert.equal(injuryTone('Questionable'), 'neutral');
  assert.equal(injuryTone('Probable'), 'neutral');
});

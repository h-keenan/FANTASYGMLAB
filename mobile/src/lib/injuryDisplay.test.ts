// Run with: node --experimental-strip-types --test src/lib/injuryDisplay.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { injuryAbbreviation, injuryTone } from './injuryDisplay.ts';

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

test('injuryAbbreviation maps common statuses to short pill codes', () => {
  assert.equal(injuryAbbreviation('Questionable'), 'Q');
  assert.equal(injuryAbbreviation('QUESTIONABLE'), 'Q');
  assert.equal(injuryAbbreviation('Doubtful'), 'D');
  assert.equal(injuryAbbreviation('Out'), 'O');
  assert.equal(injuryAbbreviation('IR'), 'IR');
  assert.equal(injuryAbbreviation('Injured Reserve'), 'IR');
  assert.equal(injuryAbbreviation('Suspended'), 'SUS');
  assert.equal(injuryAbbreviation('Sus'), 'SUS');
  assert.equal(injuryAbbreviation('PUP'), 'PUP');
});

test('injuryAbbreviation never drops an unknown status and is empty for no status', () => {
  assert.equal(injuryAbbreviation('Personal'), 'PER');
  assert.equal(injuryAbbreviation('Note'), 'NOTE');
  assert.equal(injuryAbbreviation(''), '');
  assert.equal(injuryAbbreviation(null), '');
  assert.equal(injuryAbbreviation(undefined), '');
});

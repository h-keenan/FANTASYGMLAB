import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isByeOnlyLabel, lineupStatusLabel, openSlotsMessage } from './lineupAvailability.ts';

test('bye-week player gets a Bye pill; injury label wins when present', () => {
  assert.equal(lineupStatusLabel({ injury_label: '', on_bye: true, start_ineligible_reason: 'Bye' }), 'Bye');
  assert.equal(isByeOnlyLabel({ injury_label: '', on_bye: true }), true);
  assert.equal(lineupStatusLabel({ injury_label: 'Out', on_bye: true }), 'Out');
  assert.equal(isByeOnlyLabel({ injury_label: 'Out', on_bye: true }), false);
});

test('a started game on the bench reads as Locked in the calm tone', () => {
  const locked = { injury_label: '', game_locked: true, start_ineligible_reason: 'Game started' };
  assert.equal(lineupStatusLabel(locked), 'Locked');
  assert.equal(isByeOnlyLabel(locked), true);
  assert.equal(lineupStatusLabel({ ...locked, injury_label: 'Out' }), 'Out');
  assert.equal(lineupStatusLabel({ injury_label: '', game_locked: true }), '');
});

test('older API responses without weekly fields render unchanged', () => {
  assert.equal(lineupStatusLabel({ injury_label: '' }), '');
  assert.equal(lineupStatusLabel({ injury_label: 'Questionable' }), 'Questionable');
  assert.equal(openSlotsMessage(undefined), null);
  assert.equal(openSlotsMessage([]), null);
});

test('open slots are named', () => {
  assert.match(openSlotsMessage(['QB']) ?? '', /^Open slot this week: QB\./);
  assert.match(openSlotsMessage(['RB', 'FLEX']) ?? '', /^Open slots this week: RB, FLEX\./);
});

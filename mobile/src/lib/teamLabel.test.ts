// Run with: node --experimental-strip-types --test src/lib/teamLabel.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { teamPickerLabel } from './teamLabel.ts';

test('teamPickerLabel dedupes the same name and keeps different ones', () => {
  assert.equal(teamPickerLabel("Revivalry", "coridian_"), "Revivalry · coridian_");
  assert.equal(teamPickerLabel("patrickshea", "patrickshea"), "patrickshea");
  assert.equal(teamPickerLabel(" PatrickShea ", "patrickshea"), "PatrickShea");
});

test('teamPickerLabel falls back when empty', () => {
  assert.equal(teamPickerLabel(null, undefined, "Team 4"), "Team 4");
  assert.equal(teamPickerLabel("Solo", ""), "Solo");
  assert.equal(teamPickerLabel("", "owner"), "owner");
});

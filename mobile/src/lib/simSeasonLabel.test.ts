// Run with: node --experimental-strip-types --test src/lib/simSeasonLabel.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { simSeasonLabel, simSeasonLabelForYear, simSeasonText } from './simGame.ts';

test('season number then year', () => {
  assert.equal(simSeasonLabel(3, 2028), 'S3 2028');
  assert.equal(simSeasonLabel(1), 'S1');
  assert.equal(simSeasonLabel(null, 2028), '2028');
  assert.equal(simSeasonLabel(null, null), '');
});
test('derives from the start year', () => {
  assert.equal(simSeasonLabelForYear(2028, 2026), 'S3 2028');
  assert.equal(simSeasonLabelForYear(2028, 0), '2028');
});
test('prefers the server label', () => {
  assert.equal(simSeasonText({ season_label: 'S2 2027', season_no: 9, year: 1 }), 'S2 2027');
  assert.equal(simSeasonText({ season: 2, year: 2027 }), 'S2 2027');
});

import { simOffseasonHeading, simPickLabelText, simProjNote, simProjText } from './simGame.ts';

test('offseason heading and pick labels use the season label', () => {
  assert.equal(simOffseasonHeading({ season_no: 2, seasons: 5, last_season: { year: 2027 } } as never), 'Offseason after S2 2027');
  assert.equal(simPickLabelText({ id: 'pick:2028:2:3', season: 2028, round: 2, season_label: 'S3 2028' }), 'S3 2028 Round 2');
  assert.equal(simPickLabelText({ id: 'pick:2029:2:9' }), '2029 Round 2');
});

test('bye and out are never projected', () => {
  assert.equal(simProjText({ projection: 0, projection_note: 'bye' }), 'Bye');
  assert.equal(simProjText({ projection: 0, projection_note: 'out' }), 'Out');
  assert.equal(simProjText({ projection: 12.34 }), '12.3');
  assert.equal(simProjNote({ projection_note: 'bye' }), 'Bye');
});

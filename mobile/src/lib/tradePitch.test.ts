// Run with: node --experimental-strip-types --test src/lib/tradePitch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { buildPartnerPitch, type PitchAsset } from './tradePitch.ts';

const player = (name: string, position: string, score: number): PitchAsset => ({ kind: 'player', name, position, score });
const pick: PitchAsset = { kind: 'pick', season: 2027, round: 3, score: 100 };

test('pitches value gain, position upgrade and incoming picks when supported', () => {
  const pitch = buildPartnerPitch([player('Star WR', 'WR', 5000), pick], [player('Meh WR', 'WR', 3000)], 'Rival GM');
  assert.equal(pitch.headline, 'A trade that works for Rival GM');
  assert.deepEqual(pitch.lines, ['You gain 2,100 in value', 'Upgrade at WR: Star WR', 'Adds a 2027 Round 3 pick']);
});

test('fair value within 5%; never claims a partner edge it lacks', () => {
  assert.deepEqual(buildPartnerPitch([player('A', 'QB', 1000)], [player('B', 'RB', 1030)], 'X').lines, ['Fair value both ways']);
  const sender = buildPartnerPitch([player('A', 'QB', 1000)], [player('B', 'RB', 3000)], 'X');
  assert.equal(sender.headline, 'Trade proposal for X');
  assert.doesNotMatch(sender.lines.join(' '), /gain|works for/i);
});

test('neutral proposal when no partner picked', () => {
  assert.equal(buildPartnerPitch([player('A', 'QB', 1)], [player('B', 'RB', 1)], '').headline, 'Trade proposal');
});

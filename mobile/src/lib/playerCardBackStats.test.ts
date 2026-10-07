// Run with: node --experimental-strip-types --test src/lib/playerCardBackStats.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { presentationAssetBackStats } from './playerCardBackStats.ts';
import type { PresentationAsset } from './api.ts';

function asset(overrides: Partial<PresentationAsset> = {}): PresentationAsset {
  return { asset_type: 'player', ...overrides };
}

test('empty asset -> no note, no stats', () => {
  const content = presentationAssetBackStats(asset());
  assert.equal(content.note, null);
  assert.deepEqual(content.stats, []);
});

test('tier/role/score/team/age each become their own stat row, in order', () => {
  const content = presentationAssetBackStats(
    asset({ tier: 'Elite', role: 'WR2', score: 812.4, team: 'NO', age: 30 }),
  );
  assert.deepEqual(content.stats.map((s) => s.key), ['tier', 'role', 'score', 'team_age']);
  assert.equal(content.stats[0].value, 'Elite');
  assert.equal(content.stats[1].value, 'WR2');
  // Score is rounded for display, not truncated/floored.
  assert.equal(content.stats[2].value, '812');
  assert.equal(content.stats[3].value, 'NO · Age 30');
});

test('team with no age, and age with no team, each still render', () => {
  assert.equal(presentationAssetBackStats(asset({ team: 'NO' })).stats[0].value, 'NO');
  assert.equal(presentationAssetBackStats(asset({ age: 30 })).stats[0].value, 'Age 30');
});

test('age 0 is a real age, not treated as missing', () => {
  const content = presentationAssetBackStats(asset({ age: 0 }));
  assert.equal(content.stats[0].value, 'Age 0');
});

test('score of 0 is a real score, not treated as missing', () => {
  const content = presentationAssetBackStats(asset({ score: 0 }));
  assert.equal(content.stats.find((s) => s.key === 'score')?.value, '0');
});

test('injury status alone -> warning tone (not Out/IR/Doubtful caliber)', () => {
  const content = presentationAssetBackStats(asset({ injury_status: 'Questionable' }));
  const injury = content.stats.find((s) => s.key === 'injury');
  assert.equal(injury?.value, 'Questionable');
  assert.equal(injury?.tone, 'warning');
});

test('injury status + level combine into one value string', () => {
  const content = presentationAssetBackStats(
    asset({ injury_status: 'Questionable', injury_level: 'minor' }),
  );
  assert.equal(content.stats.find((s) => s.key === 'injury')?.value, 'Questionable (minor)');
});

for (const severe of ['Out', 'IR', 'Doubtful']) {
  test(`injury status "${severe}" -> negative tone`, () => {
    const content = presentationAssetBackStats(asset({ injury_status: severe }));
    assert.equal(content.stats.find((s) => s.key === 'injury')?.tone, 'negative');
  });
}

test('opportunity_explanation becomes the note, independent of stats', () => {
  const content = presentationAssetBackStats(
    asset({ opportunity_explanation: 'Clear WR1 role with the starter out.' }),
  );
  assert.equal(content.note, 'Clear WR1 role with the starter out.');
  assert.deepEqual(content.stats, []);
});

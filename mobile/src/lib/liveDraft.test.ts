import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  diffRankMovement,
  diffTeamRankMovement,
  fairnessBandTone,
  filterLiveDraftRankings,
  formatLiveDraftScore,
  formatTradeGain,
  liveDraftDraftedPlayerOptions,
  liveDraftRankFilterOptions,
  movementGlyph,
  ranksById,
  toggleKey,
} from './liveDraft.ts';

const rows = [
  { player_id: 'a', overall_rank: 1, is_rookie: true, position: 'WR' },
  { player_id: 'b', overall_rank: 2, is_rookie: false, position: 'rb' },
];

test('filters and options', () => {
  assert.deepEqual(filterLiveDraftRankings(rows, 'Rookies').map((r) => r.player_id), ['a']);
  assert.deepEqual(filterLiveDraftRankings(rows, 'Veterans').map((r) => r.player_id), ['b']);
  assert.deepEqual(filterLiveDraftRankings(rows, 'RB').map((r) => r.player_id), ['b']);
  assert.equal(liveDraftRankFilterOptions(rows).includes('Veterans'), true);
  assert.equal(liveDraftRankFilterOptions([rows[0]]).includes('Veterans'), false);
});

test('rank movement diff and glyph', () => {
  const prev = ranksById(rows);
  const next = [{ player_id: 'a', overall_rank: 1 }, { player_id: 'b', overall_rank: 0 }, { player_id: 'c', overall_rank: 5 }];
  assert.deepEqual(diffRankMovement(next, { ...prev, a: 4 }), { a: 3, b: 2 });
  assert.deepEqual(diffTeamRankMovement([{ roster_id: 1, team_rank: 2 }], { '1': 5 }), { '1': 3 });
  assert.equal(movementGlyph(3), '▲ 3');
  assert.equal(movementGlyph(-2), '▼ 2');
  assert.equal(movementGlyph(1), '—');
});

test('formatting', () => {
  assert.equal(formatLiveDraftScore(null), '0.0');
  assert.equal(formatLiveDraftScore(12.345), '12.3');
  assert.equal(formatTradeGain(1500), '+1,500');
  assert.equal(formatTradeGain(-800), '-800');
  assert.equal(formatTradeGain(0), 'Even');
  assert.equal(fairnessBandTone('Slight Overpay'), 'warning');
  assert.equal(fairnessBandTone('Favorable'), 'success');
  assert.equal(fairnessBandTone('x'), 'neutral');
});

test('drafted options dedupe; toggleKey is immutable', () => {
  const opts = liveDraftDraftedPlayerOptions([
    { player_id: 'a', player_name: 'A', position: 'WR', fantasy_team: 'T' },
    { player_id: 'a', player_name: 'A', position: 'WR', fantasy_team: 'T' },
  ]);
  assert.equal(opts.length, 1);
  assert.equal(opts[0].label, 'A (WR · T)');
  const s = new Set(['x']);
  assert.equal(toggleKey(s, 'y').size, 2);
  assert.equal(s.size, 1);
  assert.equal(toggleKey(s, 'x').size, 0);
});

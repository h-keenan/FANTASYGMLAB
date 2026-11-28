import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

import {
  flagText,
  gapLabel,
  gapTone,
  infoText,
  lineupsSummaryLine,
  normalizeCommissionerLineups,
  setVsBestLine,
  swapLine,
  type LineupCheckTeam,
} from './commissionerLineups.ts';

function team(over: Partial<LineupCheckTeam> = {}): LineupCheckTeam {
  return {
    roster_id: '1', team_name: 'T', owner_name: null, avatar_url: null, has_lineup: true, starters: [], set_points: 90, best_points: 105.5,
    gap: 15.5, gap_pct: 0.15, partial: false, possible_tanking: true, flags: [], locked_count: 0, swaps: [], ...over,
  };
}

test('web and app copies of commissionerLineups.ts are byte-identical', () => {
  const read = (p: string) => readFileSync(resolve(process.cwd(), p), 'utf8');
  assert.equal(read('src/lib/commissionerLineups.ts'), read('../web-next/src/lib/commissionerLineups.ts'));
});

test('labels and tones: tanking is a warning, never danger', () => {
  assert.equal(gapLabel(team()), '-15.5');
  assert.equal(gapLabel(team({ gap: 0 })), 'Even');
  assert.equal(gapLabel(team({ gap: null })), 'n/a');
  assert.equal(gapTone(team()), 'warning');
  assert.equal(gapTone(team({ gap: 0, possible_tanking: false })), 'success');
  assert.equal(gapTone(team({ gap: null })), 'muted');
});

test('set vs best line handles no projections', () => {
  assert.equal(setVsBestLine(team()), 'Set 90.0 · Best 105.5');
  assert.equal(setVsBestLine(team({ set_points: null, best_points: null })), 'No projections yet');
});

test('flag and swap text', () => {
  assert.equal(flagText({ kind: 'out', label: 'Out', player: 'A. Smith', slot: 'RB' }), 'Out: A. Smith');
  assert.equal(flagText({ kind: 'empty', label: 'Empty slot', player: null, slot: 'QB' }), 'Empty QB');
  assert.equal(
    swapLine({ slot: 'RB', start: { player_id: '1', name: 'Bench Guy', position: 'RB', team: 'BUF', points: 12 }, over: null, over_reason: 'empty_slot', gain: 12 }),
    'RB: Start Bench Guy over an empty slot (+12.0)',
  );
});

test('locked hurt starters are info notes, not flags', () => {
  assert.equal(infoText({ kind: 'left_game', label: 'Left game (injury)', player: 'J. Smith', slot: 'WR' }), 'Left game (injury): J. Smith');
  const n = normalizeCommissionerLineups({ ok: true, teams: [{ roster_id: '2', info: [{ kind: 'left_game', label: 'Left game (injury)', player: 'J. Smith', slot: 'WR' }] }, { roster_id: '3' }] });
  assert.equal(n.teams[0].info?.length, 1);
  assert.equal(n.teams[0].flags.length, 0);
  assert.equal(n.teams[1].info?.length, 0);
});

test('summary line and normalizer', () => {
  assert.match(lineupsSummaryLine({ week: 5, projection_ready: false, teams: [] }), /no projections yet/);
  assert.match(lineupsSummaryLine({ week: 5, projection_ready: true, teams: [team()] }), /1 team with a big gap/);
  const n = normalizeCommissionerLineups({ ok: true, teams: [{ roster_id: '2' }] });
  assert.equal(n.teams[0].swaps.length, 0);
  assert.equal(n.projection_ready, false);
});

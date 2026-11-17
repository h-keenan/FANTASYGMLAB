import assert from 'node:assert/strict';
import { test } from 'node:test';

import { sortByStanding, standingRecord, standingsSummaryParts, standingsTitle } from './leagueStandings.ts';

const team = (roster_id: string, standing_rank: number | null, wins = 0, losses = 0, ties = 0) => ({
  roster_id,
  team_name: `T${roster_id}`,
  wins,
  losses,
  ties,
  standing_rank,
});

test('standings order, title and record text', () => {
  const ordered = sortByStanding([team('b', 2, 5, 5), team('a', 1, 8, 2, 1), team('c', null)]);
  assert.deepEqual(ordered.map((t) => t.roster_id), ['a', 'b', 'c']);
  assert.equal(standingRecord(ordered[0]), '8-2-1');
  assert.equal(standingsTitle('2026'), '2026 Standings');
  assert.equal(standingsTitle(''), 'Standings');
});

test('summary names the leader, you and the team count', () => {
  const ordered = sortByStanding([team('a', 1, 8, 2), team('b', 2, 5, 5)]);
  assert.deepEqual(standingsSummaryParts(ordered, 'b').map((p) => p.text), ['1. Ta 8-2', 'You #2 · 5-5', '2 teams']);
});

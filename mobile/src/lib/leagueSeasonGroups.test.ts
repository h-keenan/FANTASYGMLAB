import assert from 'node:assert/strict';
import { test } from 'node:test';

import { groupLeagueOptionsBySeason } from './leagueSeasonGroups.ts';

test('groups leagues by season, most recent season first', () => {
  const groups = groupLeagueOptionsBySeason([
    { league_id: 'league-2025', name: 'Dynasty Warriors', season: '2025', total_rosters: 12 },
    { league_id: 'league-2026', name: 'Dynasty Warriors', season: '2026', total_rosters: 12 },
    { league_id: 'other-2026', name: 'Other League', season: '2026', total_rosters: 10 },
  ]);

  assert.deepEqual(
    groups.map((group) => group.title),
    ['2026', '2025'],
  );
  assert.deepEqual(
    groups[0].data.map((option) => option.league_id),
    ['league-2026', 'other-2026'],
  );
  assert.deepEqual(
    groups[1].data.map((option) => option.league_id),
    ['league-2025'],
  );
});

test('returns an empty list for no leagues', () => {
  assert.deepEqual(groupLeagueOptionsBySeason([]), []);
  assert.deepEqual(groupLeagueOptionsBySeason(null), []);
  assert.deepEqual(groupLeagueOptionsBySeason(undefined), []);
});

test('keeps a league with no season label out of the numeric ordering without crashing', () => {
  const groups = groupLeagueOptionsBySeason([
    { league_id: 'a', name: 'A', season: '', total_rosters: 10 },
    { league_id: 'b', name: 'B', season: '2026', total_rosters: 10 },
  ]);

  assert.deepEqual(
    groups.map((group) => group.title),
    ['2026', 'Unknown'],
  );
});

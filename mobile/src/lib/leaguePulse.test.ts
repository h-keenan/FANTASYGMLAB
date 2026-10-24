import assert from 'node:assert/strict';
import { test } from 'node:test';

import { leaguePulseHighlights } from './leaguePulse.ts';

const t = (team_name: string, transaction_activity_count: number, current_streak: number) => ({
  team_name,
  transaction_activity_count,
  current_streak,
});

test('no highlights when nothing stands out', () => {
  assert.deepEqual(leaguePulseHighlights([]), []);
  assert.deepEqual(leaguePulseHighlights([t('A', 0, 1), t('B', 0, -1)]), []);
});

test('most active, hot, and cold leaders with web metrics', () => {
  const out = leaguePulseHighlights([t('A', 7, 3), t('B', 1, 5), t('C', 2, -2), t('D', 0, -4)]);
  assert.deepEqual(
    out.map((h) => [h.key, h.team.team_name, h.metric]),
    [
      ['most-active', 'A', '7 moves'],
      ['hot-streak', 'B', 'W5'],
      ['cold-streak', 'D', 'L4'],
    ],
  );
});

test('singular move and streak threshold of 2', () => {
  const out = leaguePulseHighlights([t('A', 1, 2)]);
  assert.deepEqual(out.map((h) => h.metric), ['1 move', 'W2']);
});

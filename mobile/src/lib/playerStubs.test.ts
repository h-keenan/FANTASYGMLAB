// Run with: node --experimental-strip-types --test src/lib/playerStubs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { waiverPlayerFromRankedPlayer } from './playerStubs.ts';

test('waiverPlayerFromRankedPlayer keeps identity/value, nulls wire-only ranks and signals', () => {
  const row = waiverPlayerFromRankedPlayer({
    player_id: '650',
    name: 'Carson Beck',
    position: 'QB',
    team: 'ARI',
    age: 24,
    status: 'Active',
    injury_status: null,
    tier: 'Depth',
    score: 120,
    overall_rank: 650,
    position_rank: 60,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 41,
  } as never);
  assert.equal(row.player_id, '650');
  assert.equal(row.score, 120);
  assert.equal(row.overall_rating, 41);
  assert.equal(row.overall_rank, null);
  assert.equal(row.position_rank, null);
  assert.equal(row.stale_free_agent, false);
  assert.equal(row.sleeper_trending_add, false);
});

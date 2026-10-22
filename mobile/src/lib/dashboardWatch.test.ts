// Run with: node --experimental-strip-types --test src/lib/dashboardWatch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { usageTrendPct, watchTagKind } from './dashboardWatch.ts';

const base = { category: 'watch', headline: 'x', reason: '' } as const;

test('usageTrendPct reads the real figure and never invents one', () => {
  assert.equal(usageTrendPct({ reason: 'Usage down 37% (high confidence) vs its earlier-season baseline.' }), 37);
  assert.equal(usageTrendPct({ reason: 'Usage trending down vs its earlier-season baseline.' }), null);
  assert.equal(usageTrendPct({ reason: 'Strong opportunity' }), null);
});

test('watchTagKind maps waiver, trending and injury items', () => {
  assert.equal(watchTagKind({ ...base, category: 'waiver_opportunity' }), 'waiver');
  assert.equal(watchTagKind({ ...base, reason: 'Usage down 13%.' }), 'trending');
  assert.equal(watchTagKind({ ...base, route_player_injury_status: 'Questionable' }), 'injury');
  assert.equal(watchTagKind({ ...base, headline: '2 injured starters' }), 'injury');
  assert.equal(watchTagKind({ ...base, category: 'league_movement' }), 'other');
});

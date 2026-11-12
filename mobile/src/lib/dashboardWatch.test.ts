// Run with: node --experimental-strip-types --test src/lib/dashboardWatch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { firstSentence, usageTrendPct, watchSummary, watchTagKind, watchTitle, watchTrendDirection } from './dashboardWatch.ts';

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

test('watch row sentences are clean and never raw feed text', () => {
  assert.equal(firstSentence('Jalen Hurts (QB) - starter | Brashard Smith (RB) - bench'), 'Jalen Hurts (QB) - starter');
  assert.equal(
    firstSentence('Monitor Gardner Minshew II. A same-team QB teammate is rising. More.'),
    'Monitor Gardner Minshew II. A same-team QB teammate is rising.',
  );
  assert.equal(watchSummary({ reason: 'x | y', route_player_injury_status: 'IR' }), 'Listed as IR; check your lineup.');
  assert.equal(watchSummary({ reason: 'Usage down 24% (high confidence).' }), 'Usage is down 24% recently.');
  assert.equal(watchTitle({ headline: 'RB' }), 'RB room');
  assert.equal(watchTitle({ headline: 'Handcuff watch' }), 'Handcuff watch');
});

test('watchTrendDirection: up for "trending up", down for usage drops and losing words', () => {
  assert.equal(watchTrendDirection({ headline: 'Taylor Exampleton is trending up', reason: 'Snap share is climbing.' }), 'up');
  assert.equal(watchTrendDirection({ headline: 'Morgan Testwell is losing usage', reason: 'Usage down 31%.' }), 'down');
  assert.equal(watchTrendDirection({ headline: 'Value is falling', reason: '' }), 'down');
});

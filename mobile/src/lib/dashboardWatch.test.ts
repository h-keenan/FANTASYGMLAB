// Run with: node --experimental-strip-types --test src/lib/dashboardWatch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { byeCover, firstSentence, usageTrendPct, watchSummary, watchTagKind, watchTitle, watchTrendDirection } from './dashboardWatch.ts';

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

test('byeCover reads the Bye Week Cover alert and never invents one', () => {
  const bye = {
    category: 'watch',
    headline: 'Your WR1 (Wade WR) is on bye in Week 9',
    reason: 'Look at the waiver wire for a fill-in: Fits One, Fits Two. You have no other healthy WR to start.',
    supporting_context: 'Bye Week Cover',
    route_player_injury_status: '',
    presentation: { bye_cover: { week: 9, slot_label: 'WR1' } },
  } as const;
  assert.deepEqual(byeCover(bye), { week: 9, slotLabel: 'WR1' });
  assert.equal(watchTagKind(bye), 'bye');
  assert.equal(watchSummary(bye), 'WR1 on bye in Week 9. Look at the waiver wire for a fill-in: Fits One, Fits Two.');
  // A Questionable bye player still reads as a bye alert, not "Listed as ...".
  assert.equal(watchSummary({ ...bye, route_player_injury_status: 'Questionable' }).startsWith('WR1 on bye'), true);
  assert.equal(byeCover({ supporting_context: 'Bye Week Cover', presentation: null }), null);
  assert.equal(byeCover({ supporting_context: 'Injury Alert', presentation: { bye_cover: { week: 9 } } }), null);
});

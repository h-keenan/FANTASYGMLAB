// Run with: node --experimental-strip-types --test src/lib/simLayout.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SIM_ASSET_ALL,
  SIM_REVIEW_VIEWS,
  simAdvanceState,
  simEmptySlotLabels,
  simLineupIssues,
  simAutoSetMessage,
  simScoreboardLabel,
  simMatchupStatus,
  simMatchupMargin,
  simFilterGroups,
  simGroupByPosition,
  simLineupDiff,
  simOpenKey,
  simParseOpen,
  simPreview,
  simReviewViewFor,
  simSeeAllLabel,
  simSideSummary,
  simTradeFit,
  simWindow,
} from './simLayout.ts';

test('open state keys and parsing', () => {
  assert.equal(simOpenKey('home.injuries'), 'fgl:sim-open:home.injuries');
  assert.equal(simParseOpen('1', false), true);
  assert.equal(simParseOpen('0', true), false);
  assert.equal(simParseOpen(null, true), true);
});

test('previews and windows long lists', () => {
  assert.deepEqual(simPreview([1, 2, 3, 4, 5], false, 3), { shown: [1, 2, 3], hidden: 2 });
  assert.equal(simPreview([1, 2], false, 3).hidden, 0);
  assert.equal(simSeeAllLabel(2, false, 'players'), 'See all (2 players)');
  assert.equal(simSeeAllLabel(2, true), 'Show less');
  assert.equal(simWindow(Array.from({ length: 50 }, (_, i) => i), 20).remaining, 30);
});

test('every review section lands on a tab', () => {
  const tabs = new Set(SIM_REVIEW_VIEWS.map((v) => v.value));
  for (const id of ['grade', 'decisions', 'moves', 'swings', 'injuries', 'champion-path', 'your-path', 'journey', 'stats', 'leaders', 'your-leaders', 'closest-yours', 'closest-league']) {
    assert.ok(tabs.has(simReviewViewFor(id)));
  }
  assert.equal(simReviewViewFor('swings'), 'awards');
  assert.equal(simReviewViewFor('mystery'), 'overview');
});

test('trade picker groups, filters and fit', () => {
  const roster = [
    { id: '1', name: 'Quinn Back', pos: 'QB', value: 80 },
    { id: '2', name: 'Ray Runner', pos: 'RB', value: 60.4 },
    { id: '3', name: 'Rob Rush', pos: 'RB', value: 40 },
  ];
  const groups = simGroupByPosition(roster, ['QB', 'RB', 'WR']);
  assert.deepEqual(groups.map((g) => [g.key, g.items.length]), [['QB', 1], ['RB', 2]]);
  assert.deepEqual(simFilterGroups(groups, SIM_ASSET_ALL, 'rush').map((g) => g.items[0].id), ['3']);
  assert.deepEqual(simSideSummary(roster.slice(0, 2)), { count: 2, value: 140 });
  assert.deepEqual(simTradeFit(16, 16, 1, 3), { after: 18, room: 0, over: 2 });
});

test('auto-set message and advance state', () => {
  const a = (id: string, name: string) => ({ id, name });
  const before = [{ slot: 'RB', player: a('2', 'Hurt Harry') }];
  const after = [{ slot: 'RB', player: a('3', 'Wally Wire') }];
  assert.equal(simAutoSetMessage(simLineupDiff(before, after, 100, 107.54)), 'Swapped Hurt Harry for Wally Wire, +7.5 proj');
  assert.equal(simAutoSetMessage(simLineupDiff(after, after, 1, 1)), 'Lineup is optimal');
  const one = simAdvanceState({ phase: 'regular_season', week: 4 }, ['WR2']);
  assert.equal(one.blocked, false);
  assert.equal(one.reason, null);
  assert.equal(one.confirm, 'WR2 is empty and will score 0 unless a healthy bench player fits. Advance anyway?');
  assert.deepEqual(simEmptySlotLabels([{ slot: 'QB', player: {} }, { slot: 'WR', player: {} }, { slot: 'WR', player: null }]), ['WR2']);
  assert.equal(simAdvanceState({ phase: 'regular_season', week: 4, pending: { cuts_needed: 2 } }, 0).reason, 'Cut 2 players first');
});

test('the advance bar warns only from the current lineup: filled WR2 is never empty, bye/out starters are separate', () => {
  const before = [{ slot: 'QB', player: { id: 'q', name: 'Q' } }, { slot: 'WR', player: { id: 'w1', name: 'W1' } }, { slot: 'WR', player: null }];
  assert.deepEqual(simLineupIssues(before, []).empty, ['WR2']);
  // after a set-lineup / auto-set fills the slot, the next lineup response has no empty slot
  const after = [before[0], before[1], { slot: 'WR', player: { id: 'w2', name: 'Jakobi Meyers' } }];
  assert.deepEqual(simLineupIssues(after, []).empty, []);
  assert.equal(simAdvanceState({ week: 2 }, simLineupIssues(after, []).empty, []).confirm, null);
  const out = simLineupIssues(after, [{ code: 'out', player_id: 'w2' }, { code: 'empty_slot', player_id: null }]);
  assert.deepEqual(out.empty, []);
  assert.deepEqual(out.zero, [{ label: 'WR2', name: 'Jakobi Meyers', reason: 'out' }]);
  const state = simAdvanceState({ week: 2 }, out.empty, out.zero);
  assert.equal(state.confirm, 'Jakobi Meyers (WR2) is out and will score 0 unless you swap him. Advance anyway?');
  const both = simAdvanceState({ week: 2 }, ['WR1'], [{ label: 'RB', name: 'A', reason: 'bye' }]);
  assert.match(both.confirm ?? '', /WR1 is empty .* A \(RB\) is on a bye and will score 0/);
});

test('auto-set never says optimal while a slot is empty or a starter is on a bye/out', () => {
  const same = { swaps: [], gain: 0 };
  assert.equal(simAutoSetMessage(same), 'Lineup is optimal');
  assert.equal(simAutoSetMessage(same, { empty: [], zero: [] }), 'Lineup is optimal');
  assert.match(simAutoSetMessage(same, { empty: ['QB'], zero: [] }), /^Nothing to swap\. No QB on your roster to start in QB\. Claim one from the Players tab\.$/);
  assert.match(simAutoSetMessage(same, { empty: ['FLEX'], zero: [] }), /No RB, WR or TE on your roster/);
  assert.match(simAutoSetMessage(same, { empty: [], zero: [{ label: 'WR1', name: 'C. Watson', reason: 'bye' }] }), /C\. Watson \(WR1\) is on a bye and no healthier player fits/);
  const four = { swaps: [{ slot: 'RB', out: 'a', in: 'b' }, { slot: 'WR', out: 'c', in: 'd' }, { slot: 'TE', out: 'e', in: 'f' }, { slot: 'K', out: 'g', in: 'h' }], gain: 3.2 };
  assert.equal(simAutoSetMessage(four, { empty: [], zero: [] }), 'Made 4 lineup swaps, +3.2 proj');
  assert.match(simAutoSetMessage(four, { empty: ['QB'], zero: [] }), /^Made 4 lineup swaps, \+3\.2 proj\. No QB on your roster/);
});

test('scoreboard label never duplicates the week; matchup status and margin', () => {
  assert.equal(simScoreboardLabel('Week 10', 10), 'Week 10');
  assert.equal(simScoreboardLabel('Semifinal', 15), 'Semifinal · Week 15');
  assert.deepEqual(simMatchupStatus({ home_pts: 68.9, away_pts: 140.7, winner: 'b' }), { key: 'final', label: 'FINAL', tone: 'success' });
  assert.equal(simMatchupStatus({ home_pts: null, away_pts: null, winner: null }).key, 'upcoming');
  const names = { a: 'Boom or Bust', b: 'Flex Appeal' };
  assert.equal(simMatchupMargin({ home: 'a', away: 'b', home_pts: 68.9, away_pts: 140.7 }, names), 'Flex Appeal won by 71.8');
  assert.equal(simMatchupMargin({ home: 'a', away: 'b', home_pts: 90, away_pts: 90 }, names), 'Tie');
  assert.equal(simMatchupMargin({ home: 'a', away: 'b', home_pts: null, away_pts: null }, names), 'Not played yet');
});

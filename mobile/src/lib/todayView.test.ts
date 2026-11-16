import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildDecisionQueue, lineupSwaps, type DecisionMove } from './decisionQueue.ts';
import {
  matchupPlanParams,
  parseMatchupPlan,
  todayAlertsSummary,
  todayFixAll,
  todayMatchupRing,
  todayRoomChips,
  todayTiles,
  todayTradeIdea,
} from './todayView.ts';
import { slotsWithSwap } from './matchupPlanner.ts';

const p = (id: string, name: string, injury = '') => ({ player_id: id, name, position: 'RB', team: 'BUF', tier: 'starter', injury_label: injury });
const move = (over: Partial<DecisionMove> & { out: string; inn: string; injury?: string }): DecisionMove => ({
  start: p(over.inn, `Sub ${over.inn}`),
  over: p(over.out, `Out ${over.out}`, over.injury ?? ''),
  over_reason: 'over_reason' in over ? (over.over_reason as DecisionMove['over_reason']) : 'ruled_out',
  gain: over.gain ?? 5,
  locked: over.locked ?? false,
});

test('lineupSwaps: one row per fixable problem, biggest gain first, locked moves never offered', () => {
  const swaps = lineupSwaps([
    move({ out: 'a', inn: 's1', gain: 4 }),
    move({ out: 'b', inn: 's2', gain: 11.2, over_reason: 'bye_week' }),
    move({ out: 'c', inn: 's3', gain: 14, locked: true }),
    move({ out: 'd', inn: 's4', gain: 9, over_reason: null, injury: 'Questionable' }),
    // A projection-only swap (healthy starter) is not a lineup problem.
    move({ out: 'e', inn: 's5', gain: 3, over_reason: null }),
  ]);
  assert.deepEqual(swaps.map((s) => s.out?.id), ['b', 'd', 'a']);
  assert.equal(swaps[0].status, 'BYE');
  assert.equal(swaps[1].status, 'Questionable');
  assert.equal(swaps[1].tone, 'warning');
  assert.ok(!swaps.some((s) => s.out?.id === 'c'));
});

test('the lineup decision carries the swaps; injured starters with no swap never read as "nothing needs you"', () => {
  const q = buildDecisionQueue({
    now: new Date(2026, 10, 9, 12),
    moves: [move({ out: 'a', inn: 's1', gain: 4 }), move({ out: 'd', inn: 's4', gain: 9, over_reason: null, injury: 'Questionable' })],
    thisWeek: null,
    items: [],
    tradeWindow: null,
  });
  assert.equal(q.all[0].kind, 'lineup');
  assert.equal(q.all[0].swaps.length, 2);
  const empty = buildDecisionQueue({ now: new Date(2026, 10, 9, 12), moves: [], thisWeek: null, items: [], tradeWindow: null, injuredStarters: 3 });
  assert.equal(empty.total, 0);
  assert.equal(empty.empty?.title, 'No better lineup swaps');
  const quiet = buildDecisionQueue({ now: new Date(2026, 10, 9, 12), moves: [], thisWeek: null, items: [], tradeWindow: null, injuredStarters: 0 });
  assert.equal(quiet.empty?.title, 'Nothing needs you this week');
});

test('todayFixAll sums the gains and needs two swaps', () => {
  assert.equal(todayFixAll([{ gain: 5 }]), null);
  assert.deepEqual(todayFixAll([{ gain: 11.2 }, { gain: 9.8 }, { gain: null }]), { count: 3, total: 21, label: 'Fix all 3 · +21.0 proj' });
});

test('matchup plan params round-trip and fall back to every move', () => {
  const swap = { out: { id: 'o1' }, replacement: { id: 's1' } } as never;
  assert.deepEqual(matchupPlanParams(swap), { plan: 'swap', out: 'o1', in: 's1' });
  assert.deepEqual(matchupPlanParams(null), { plan: 'all' });
  assert.deepEqual(parseMatchupPlan({ plan: 'swap', out: 'o1', in: 's1' }), { kind: 'swap', out: 'o1', in: 's1' });
  assert.deepEqual(parseMatchupPlan({ plan: 'swap' }), { kind: 'all' });
  assert.equal(parseMatchupPlan({ plan: 'nope' }), null);
  assert.equal(parseMatchupPlan({}), null);
});

test('slotsWithSwap puts the bench player in the starter slot, trading places when he already starts', () => {
  const slots = [
    { slot: 'RB', player_id: 'o1' },
    { slot: 'FLEX', player_id: 'b1' },
  ];
  assert.deepEqual(slotsWithSwap(slots, 'o1', 's1'), [{ slot: 'RB', player_id: 's1' }, { slot: 'FLEX', player_id: 'b1' }]);
  assert.deepEqual(slotsWithSwap(slots, 'o1', 'b1'), [{ slot: 'RB', player_id: 'b1' }, { slot: 'FLEX', player_id: 'o1' }]);
  assert.equal(slotsWithSwap(slots, 'zz', 's1'), null);
});

test('todayMatchupRing: ring, kicker, score line and trailing chip', () => {
  const ring = todayMatchupRing({ week: 10, opponentName: 'Shiesty', opponentAvatar: null, myName: 'GG', myAvatar: null, winPercent: 3, myProjected: 109.7, opponentProjected: 136.9, live: null, stateLabel: null });
  assert.equal(ring.pct, 3);
  assert.equal(ring.tone, 'danger');
  assert.equal(ring.kicker, 'WK 10 · VS SHIESTY');
  assert.equal(ring.scoreLine, '109.7 vs 136.9');
  assert.equal(ring.scoreCaption, 'projected');
  assert.deepEqual(ring.chip, { label: 'trailing 27.2', tone: 'danger' });
  const live = todayMatchupRing({ week: 10, opponentName: 'Shiesty', opponentAvatar: null, myName: 'GG', myAvatar: null, winPercent: null, myProjected: null, opponentProjected: null, live: { mine: 80, opponent: 75 }, stateLabel: 'Live' });
  assert.equal(live.scoreCaption, 'live');
  assert.equal(live.chip?.label, 'leading 5.0');
  assert.ok(live.kicker.endsWith('LIVE'));
});

test('todayTiles: standing and odds from one model, trades closed or counted, no zero-filling', () => {
  const standing = { record: '3-6', place: '8th of 12', playoffStatus: null, powerRank: null, playoffOdds: '1%', projectedRecord: null, tone: 'neutral' as const };
  const tiles = todayTiles({ standing, tradeCount: 1 });
  assert.deepEqual(tiles.map((t) => [t.key, t.value, t.sub]), [['standing', '8th', 'of 12 · 3-6'], ['playoffs', '1%', 'odds'], ['trades', '1', 'idea']]);
  assert.equal(tiles[1].tone, 'danger');
  assert.deepEqual(todayTiles({ standing: null, tradeCount: 0 }), []);
  assert.equal(todayTiles({ standing: null, tradeCount: 3, tradesClosed: true })[0].value, 'Closed');
});

test('todayRoomChips: marks and qualitative meter fill', () => {
  const chips = todayRoomChips([
    { position: 'QB', label: 'Needs help', tone: 'risk', weakest: true },
    { position: 'TE', label: 'Solid', tone: 'neutral', weakest: false },
  ]);
  assert.equal(chips[0].mark, '!');
  assert.equal(chips[0].tone, 'danger');
  assert.equal(chips[1].mark, 'check');
  assert.ok(chips[0].fill < chips[1].fill);
});

test('todayTradeIdea reads the real package; no package, no card', () => {
  const idea = todayTradeIdea({
    headline: 'x',
    presentation: {
      trade_package: { send: [{ asset_type: 'player', player_id: '1', name: 'R. Walsh', position: 'RB' }], receive: [{ asset_type: 'player', player_id: '2', name: 'C. Murray', position: 'QB' }] },
      partner_team_name: 'Team Iron',
      trade_gain: 450,
    },
  });
  assert.equal(idea?.title, 'Get a QB from Team Iron');
  assert.equal(idea?.gain, 450);
  assert.equal(todayTradeIdea({ headline: 'x', presentation: null }), null);
  const rb = todayTradeIdea({ headline: 'x', presentation: { trade_package: { send: [], receive: [{ asset_type: 'player', name: 'A', position: 'RB' }] }, partner_team_name: 'T' } });
  assert.equal(rb?.title, 'Get an RB from T');
});

test('todayAlertsSummary: distinct avatars, newest headline, how many more', () => {
  const line = (id: string | null, title: string) => ({ playerId: id, name: id, position: null, team: null, tier: null, title });
  const s = todayAlertsSummary([line('a', 'A out'), line('a', 'A again'), line('b', 'B'), line(null, 'League news')]);
  assert.deepEqual(s.avatars.map((a) => a.playerId), ['a', 'b']);
  assert.equal(s.lead, 'A out');
  assert.equal(s.more, 3);
});

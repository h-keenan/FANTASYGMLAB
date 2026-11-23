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
  bestTradeIdea,
  tradeGainLabel,
  todayActionRow,
  todayActions,
  todayAlertRows,
  todayMatchupMove,
  todayStandingLine,
  TODAY_ACTION_CAP,
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

test('todayTiles: standing, odds and team rank from one model, no zero-filling, no trades tile', () => {
  const standing = { record: '3-6', place: '8th of 12', playoffStatus: null, powerRank: null, playoffOdds: '1%', projectedRecord: null, tone: 'neutral' as const };
  const tiles = todayTiles({ standing, teamRank: { value: '#3', of: 12 } });
  assert.deepEqual(tiles.map((t) => [t.key, t.value, t.sub]), [['standing', '8th', 'of 12 · 3-6'], ['playoffs', '1%', 'odds'], ['rank', '#3', 'of 12']]);
  assert.equal(tiles[1].tone, 'danger');
  assert.deepEqual(todayTiles({ standing: null }), []);
  assert.deepEqual(todayTiles({ standing: null, teamRank: { value: '—', of: 12 } }), []);
});

test('bestTradeIdea: biggest positive gain leads; a negative idea is never the headline or shown', () => {
  const mk = (gain: number | null) => ({ title: 't', send: [], receive: [], gain });
  assert.equal(bestTradeIdea([mk(-125), mk(40), mk(300)])?.gain, 300);
  assert.equal(bestTradeIdea([mk(-125), mk(0)]), null);
  assert.equal(bestTradeIdea([mk(-125), mk(null)])?.gain, null);
  assert.equal(bestTradeIdea([]), null);
  assert.equal(tradeGainLabel(mk(1234)), '+1,234');
  assert.equal(tradeGainLabel(mk(-125)), null);
});

test('todayActionRow: one short line per decision, lineup swaps collapse to one row', () => {
  const p = (name: string) => ({ id: name, name, position: 'WR', team: null, tier: null, injuryStatus: null, note: null, stat: null });
  const swap = (name: string, gain: number | null) => ({ key: name, out: p(name), status: 'OUT', reason: '', tone: 'danger' as const, replacement: p('Sam Ortiz'), gain });
  const base = { key: 'k', kind: 'lineup' as const, tone: 'danger' as const, title: 'x', players: [], primary: { label: 'Open', target: 'matchup' as const } };
  assert.equal(todayActionRow({ ...base, swaps: [swap('Ray Reyes', 4)] }).reason, 'Reyes out, start Ortiz');
  const many = todayActionRow({ ...base, swaps: [swap('A B', 4), swap('C D', 2.5)] });
  assert.equal(many.reason, '2 lineup swaps · +6.5');
  assert.equal(many.button, 'Fix all');
  const waiver = todayActionRow({ ...base, kind: 'waiver', swaps: [], players: [p('Gibbs')], title: 'Add Jahmyr Gibbs before waivers run tonight at midnight', primary: { label: 'Bid', target: 'waivers' as const } });
  assert.equal(waiver.reason.split(' ').length <= 6, true);
  assert.equal(waiver.player?.name, 'Gibbs');
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

const baseQueue = (moves: DecisionMove[], items: Parameters<typeof buildDecisionQueue>[0]['items'] = []) =>
  buildDecisionQueue({ now: new Date('2026-11-18T12:00:00'), moves, thisWeek: null, items, tradeWindow: null });

const tradeIdea = todayTradeIdea({
  headline: 'Swap',
  presentation: { trade_package: { send: [{ asset_type: 'player', player_id: '1', name: 'R. Walsh', position: 'RB' }], receive: [{ asset_type: 'player', player_id: '2', name: 'C. Murray', position: 'QB' }] }, partner_team_name: 'Team Iron', trade_gain: 300 },
});

test('todayMatchupMove: the biggest-gain swap as one line; null without a fix', () => {
  const q = baseQueue([move({ out: 'o1', inn: 's1', gain: 4 }), move({ out: 'o2', inn: 's2', gain: 9 })]);
  const best = todayMatchupMove(q.all.find((d) => d.kind === 'lineup')?.swaps);
  assert.equal(best?.text, 'Start s2 over o2 (+9.0)');
  assert.equal(best?.swap.out?.id, 'o2');
  assert.equal(todayMatchupMove([]), null);
});

test('todayActions: each lineup fix is its own row, ranked by urgency, the best trade joins, capped with a total', () => {
  const moves = Array.from({ length: 6 }, (_, i) => move({ out: `o${i}`, inn: `s${i}`, gain: 10 - i }));
  const all = todayActions(baseQueue(moves), tradeIdea);
  assert.equal(all.total, 7);
  assert.equal(all.rows.length, TODAY_ACTION_CAP);
  assert.deepEqual(all.rows.map((r) => r.kind), ['swap', 'swap', 'swap', 'swap', 'swap']);
  assert.equal(all.rows[0].button, 'Swap');
  assert.equal(all.rows[0].player?.id, 'o0');
  const small = todayActions(baseQueue([move({ out: 'o1', inn: 's1' })]), tradeIdea);
  assert.deepEqual(small.rows.map((r) => r.kind), ['swap', 'trade']);
  const trade = small.rows[1];
  assert.equal(trade.button, 'Send offer');
  assert.equal(trade.player?.name, 'C. Murray');
  assert.equal(trade.reason, 'Get a QB from Team Iron');
  assert.equal(todayActions(baseQueue([]), null).total, 0);
});

test('todayActions: an empty slot reads Fill and a trade never outranks a hurt starter', () => {
  const q = baseQueue([{ start: p('s9', 'Sam Nine'), over: null, over_reason: 'empty_slot', gain: 3, locked: false }]);
  const { rows } = todayActions(q, tradeIdea);
  assert.equal(rows[0].button, 'Fill');
  assert.equal(rows[0].player, null);
  assert.equal(rows[1].kind, 'trade');
});

const alertOf = (over: Partial<Parameters<typeof todayAlertRows>[0][number]>) => ({
  alert_key: 'k', title: 'Reyes ejected', link: null, event_type: 'injury/status', read: false, matched_player: 'Jordan Reyes', matched_player_id: 'p1', matched_player_position: 'RB', matched_player_team: 'BUF', matched_player_tier: 'starter', roster_relationship: 'starter' as const, ...over,
});

test('todayAlertRows: only rostered players; starters get Swap / Lineup, bench news needs a story to Read', () => {
  const { rows, total } = todayAlertRows([
    alertOf({ alert_key: 'league', matched_player_id: null, roster_relationship: null }),
    alertOf({ alert_key: 'bench-nolink', matched_player_id: 'p2', roster_relationship: 'bench' }),
    alertOf({ alert_key: 'bench', matched_player_id: 'p3', roster_relationship: 'bench', link: 'https://x.test/s', read: true }),
    alertOf({ alert_key: 'role', matched_player_id: 'p4', event_type: 'role/depth chart', read: true }),
    alertOf({ alert_key: 'hurt', matched_player_id: 'p5' }),
  ]);
  assert.equal(total, 3);
  assert.deepEqual(rows.map((r) => [r.alertKey, r.button, r.target]), [['hurt', 'Swap', 'matchup'], ['role', 'Lineup', 'matchup'], ['bench', 'Read', 'link']]);
});

test('todayStandingLine: the tiles on one line', () => {
  const tiles = todayTiles({ standing: { place: '8th of 12', record: '6-4', playoffOdds: '72%', tone: 'neutral' } as never, teamRank: { value: '#3', of: 12 } });
  assert.deepEqual(todayStandingLine(tiles).map((p) => p.text), ['8th of 12 · 6-4', 'Playoffs 72%', 'Rank #3']);
});

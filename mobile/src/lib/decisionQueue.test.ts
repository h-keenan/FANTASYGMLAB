import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildDecisionQueue, seeAllLabel, type DecisionInput, type DecisionItem } from './decisionQueue.ts';

const mon = new Date(2026, 10, 9, 12);
const p = (id: string, name: string) => ({ player_id: id, name, position: 'RB', team: 'BUF', tier: 'starter', injury_label: '' });
const item = (over: Partial<DecisionItem> = {}): DecisionItem => ({
  category: 'top_priority', headline: 'Something', reason: 'Because', destination: 'gm_plan', route_player_id: '', route_player_name: '',
  route_player_position: '', route_player_team: '', route_player_tier: '', route_player_score: null, route_player_injury_status: '',
  mentioned_players: [], presentation: null, ...over,
});
const base = (over: Partial<DecisionInput> = {}): DecisionInput => ({ now: mon, moves: [], thisWeek: null, items: [], tradeWindow: null, ...over });

test('lineup holes are one decision with player rows and gain', () => {
  const q = buildDecisionQueue(base({ moves: [{ start: p('s', 'Sub'), over: p('o', 'Out Guy'), over_reason: 'bye_week', gain: 4.1, locked: false }] }));
  assert.equal(q.all.length, 1);
  assert.equal(q.all[0].kind, 'lineup');
  assert.deepEqual(q.all[0].players[0].stat, { value: '+4.1', label: 'GAIN' });
});

test('the lineup issue appears once (injury alert on a hole player is dropped)', () => {
  const q = buildDecisionQueue(base({
    moves: [{ start: p('s', 'Sub'), over: p('o', 'Out Guy'), over_reason: 'ruled_out', gain: 1, locked: false }],
    items: [item({ headline: 'Out Guy is out', route_player_id: 'o', route_player_name: 'Out Guy', route_player_injury_status: 'Out' })],
  }));
  assert.deepEqual(q.all.map((d) => d.kind), ['lineup']);
});

test('deadline this week, waiver merge, live draft ordering', () => {
  const q = buildDecisionQueue(base({
    tradeWindow: { trade_deadline_week: 9, current_week: 9, trade_deadline_passed: false },
    thisWeek: { week: 9, rows: [{ key: 'waiver', status: 'Add', tone: 'waiver', headline: 'Add', why: 'thin', cta_label: 'Open', route: 'waivers', player_id: 'w' }], next_action: { headline: 'Live', why: 'now', cta_label: 'Join', route: 'live_draft' } },
    items: [item({ headline: 'Claim W', destination: 'waivers', route_player_id: 'w', route_player_name: 'Wes Wire' })],
  }));
  assert.deepEqual(q.all.map((d) => d.kind), ['live_draft', 'deadline', 'waiver']);
});

test('caps at 3 with See all (N); free gating and empty state', () => {
  const items = Array.from({ length: 5 }, (_, i) => item({ headline: `Item ${i}`, route_player_score: 50 - i }));
  const q = buildDecisionQueue(base({ items, entitlement: { isPremium: false, hiddenCount: 2 } }));
  assert.equal(q.visible.length, 3);
  assert.equal(seeAllLabel(q, false), 'See all (5)');
  assert.deepEqual(q.proUpsell, { hidden: 2 });
  const empty = buildDecisionQueue(base({ nextGame: { week: 7, opponentName: 'Mock Mavericks' } }));
  assert.deepEqual(empty.empty, { title: 'Nothing needs you this week', detail: 'Next up: Week 7 vs Mock Mavericks' });
});

// Run with: node --experimental-strip-types --test src/lib/todayPlan.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { buildTodayPlan, todayTitle } from './todayPlan.ts';

const row = (key: string, over: Record<string, unknown> = {}): any => ({
  key, status: 'S', tone: 'neutral', headline: key, why: 'w', cta_label: 'go', route: 'matchup', player_id: '', ...over,
});
const wk = (rows: any[]): any => ({ mode: 'in_season', week: 3, rows, next_action: null });
const card = (over: Record<string, unknown> = {}): any => ({
  category: 'top_priority', headline: 'H', destination: 'my_team', route_player_id: '', ...over,
});
const SUN = new Date(2026, 9, 25, 12);
const WED = new Date(2026, 9, 21, 12);
const keys = (p: ReturnType<typeof buildTodayPlan>) => p.today.map((e) => (e.kind === 'row' ? e.row.key : 'card'));

test('game day: lineup today, waiver and trade later', () => {
  const p = buildTodayPlan(wk([row('lineup'), row('waiver'), row('trade')]), [], SUN);
  assert.deepEqual(keys(p), ['lineup']);
  assert.deepEqual(p.later.map((r) => r.key), ['waiver', 'trade']);
});

test('waiver day: waiver today, healthy lineup later, risk lineup still first', () => {
  assert.deepEqual(keys(buildTodayPlan(wk([row('lineup'), row('waiver')]), [], WED)), ['waiver']);
  const r = buildTodayPlan(wk([row('lineup', { tone: 'risk' }), row('waiver')]), [card()], WED);
  assert.deepEqual(keys(r), ['lineup', 'card', 'waiver']);
});

test('dedupes trade card vs row and waiver row vs waiver card; ignores non top-priority', () => {
  const trade = row('trade', { status: 'Idea', headline: 'Idea X' });
  const p = buildTodayPlan(
    wk([trade, row('waiver', { player_id: '9' })]),
    [card({ headline: 'Idea X' }), card({ headline: 'Add', destination: 'waivers', route_player_id: '9' }), card({ category: 'watch' })],
    WED,
  );
  assert.equal(p.dropped.items.length, 1);
  assert.deepEqual(p.dropped.rows.map((r) => r.key), ['waiver']);
  assert.equal(p.today.filter((e) => e.kind === 'card').length, 1);
});

test('empty and title', () => {
  assert.equal(buildTodayPlan(null, [], SUN).isEmpty, true);
  assert.equal(todayTitle(wk([])), 'Today · Week 3');
  assert.equal(todayTitle(null), 'Today');
});

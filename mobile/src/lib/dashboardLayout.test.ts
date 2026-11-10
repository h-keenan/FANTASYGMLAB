import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

import {
  DASHBOARD_MODULE_ORDER,
  buildNeedsAttention,
  buildNowChips,
  deadlineChip,
  isTradeItem,
  itemsAfterAttention,
  normalizeAlertTitle,
  nextMoveRowFilter,
  tradeIdeasLine,
  weekRowsAfterAttention,
} from './dashboardLayout.ts';

function shared(path: string): string {
  const text = readFileSync(resolve(process.cwd(), path), 'utf8');
  const start = text.indexOf('// SHARED BEGIN');
  const end = text.indexOf('// SHARED END');
  assert.ok(start >= 0 && end > start, `${path} missing SHARED markers`);
  return text.slice(start, end);
}

test('web and app share one Dashboard layout block', () => {
  assert.equal(shared('src/lib/dashboardLayout.ts'), shared('../web-next/src/lib/dashboardLayout.ts'));
});

test('module order: at a glance, needs attention, this week, then the one-line trade pointer', () => {
  assert.deepEqual(DASHBOARD_MODULE_ORDER.slice(0, 5), ['start_here', 'now', 'needs_attention', 'next_moves', 'trades']);
  assert.equal(DASHBOARD_MODULE_ORDER[DASHBOARD_MODULE_ORDER.length - 1], 'more');
});

test('deadline chip is real data only', () => {
  assert.equal(deadlineChip(null), null);
  assert.equal(deadlineChip({ trade_deadline_week: null, current_week: 5, trade_deadline_passed: false }), null);
  assert.equal(deadlineChip({ trade_deadline_week: 11, current_week: 12, trade_deadline_passed: true }), null);
  assert.equal(deadlineChip({ trade_deadline_week: 11, current_week: 8, trade_deadline_passed: false })?.value, '3 wks left (Wk 11)');
  assert.equal(deadlineChip({ trade_deadline_week: 11, current_week: 11, trade_deadline_passed: false })?.tone, 'risk');
  assert.equal(deadlineChip({ trade_deadline_week: 11, current_week: null, trade_deadline_passed: false })?.value, 'Week 11');
});

test('now chips and next-move filter drop duplicates', () => {
  const rows = [
    { key: 'lineup', status: 'Set', tone: 'positive' },
    { key: 'waiver', status: 'Add', tone: 'waiver' },
    { key: 'trade', status: 'Idea', tone: 'trade' },
  ];
  assert.deepEqual(buildNowChips(rows, null, 2).map((c) => c.key), ['lineup', 'alerts', 'waivers']);
  assert.deepEqual(rows.filter(nextMoveRowFilter).map((r) => r.key), ['waiver']);
  assert.equal(nextMoveRowFilter({ key: 'lineup', status: 'Out', tone: 'risk' }), true);
  assert.equal(isTradeItem({ presentation: { trade_package: {} } }), true);
  assert.equal(isTradeItem({ presentation: null }), false);
});

const row = (key: string, tone: string, extra: object = {}) => ({ key, status: 'Out', tone, headline: `${key} headline`, why: 'because', ...extra });
const item = (headline: string, trade = false) => ({
  headline,
  reason: 'why',
  destination: 'waivers',
  presentation: trade ? { trade_package: {} } : null,
});

test('needs attention reads only existing urgency fields, capped at 3, never trade ideas', () => {
  assert.deepEqual(buildNeedsAttention([row('lineup', 'positive')], null, []), []);
  const entries = buildNeedsAttention(
    [row('lineup', 'risk')],
    { trade_deadline_week: 11, current_week: 10, trade_deadline_passed: false },
    [item('Trade idea', true), item('A'), item('B')],
  );
  assert.deepEqual(entries.map((e) => e.source), ['lineup', 'deadline', 'item']);
  assert.equal(entries[0].target, 'matchup');
  assert.equal(entries[1].target, 'gm_plan');
  assert.equal(entries[2].item?.headline, 'A');
  // A far-off deadline is not urgent.
  assert.deepEqual(buildNeedsAttention([], { trade_deadline_week: 11, current_week: 5, trade_deadline_passed: false }, []), []);
});

test('items shown under needs attention are not repeated in the chips or this-week rows', () => {
  const attention = buildNeedsAttention([row('lineup', 'risk')], { trade_deadline_week: 11, current_week: 11, trade_deadline_passed: false }, []);
  const keys = buildNowChips([row('lineup', 'risk')], { trade_deadline_week: 11, current_week: 11, trade_deadline_passed: false }, 0, attention.map((e) => e.source)).map((c) => c.key);
  assert.deepEqual(keys, []);
  assert.deepEqual(weekRowsAfterAttention([row('lineup', 'risk'), row('waiver', 'waiver')], attention).map((r) => r.key), ['waiver']);
  assert.deepEqual(weekRowsAfterAttention([row('lineup', 'risk')], []).map((r) => r.key), ['lineup']);
});

test('trade ideas line is a count, never cards', () => {
  assert.equal(tradeIdeasLine(1, false, false), '1 trade idea');
  assert.equal(tradeIdeasLine(3, false, false), '3 trade ideas');
  assert.match(tradeIdeasLine(0, false, false), /No trade idea/);
  assert.match(tradeIdeasLine(2, true, false), /deadline has passed/);
});

test('the same alert never shows in Needs attention and This week', () => {
  assert.equal(normalizeAlertTitle('Check Matchup: Darnell Washington is on a bye (+1 more)'), 'check matchup darnell washington is on a bye');
  const attention = [{ headline: 'Check Matchup: Darnell Washington is on a bye (+1 more)' }];
  const kept = itemsAfterAttention(
    [{ headline: 'check matchup - darnell washington is on a BYE' }, { headline: 'Other' }],
    attention,
  );
  assert.deepEqual(kept.map((i) => i.headline), ['Other']);
});

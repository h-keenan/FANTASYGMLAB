import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

import {
  DASHBOARD_MODULE_ORDER,
  buildNowChips,
  deadlineChip,
  isTradeItem,
  nextMoveRowFilter,
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

test('module order leads with what matters now, then trades', () => {
  assert.deepEqual(DASHBOARD_MODULE_ORDER.slice(0, 3), ['start_here', 'now', 'trades']);
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

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

import {
  DEADLINE_CLOSED_COPY,
  deadlineCopy,
  deadlinePosture,
  deadlineState,
  showDeadlineCard,
} from './deadlineMode.ts';

function shared(path: string): string {
  const text = readFileSync(resolve(process.cwd(), path), 'utf8');
  const start = text.indexOf('// SHARED BEGIN');
  const end = text.indexOf('// SHARED END');
  assert.ok(start >= 0 && end > start, `${path} missing SHARED markers`);
  return text.slice(start, end);
}

const win = (week: number | null, current: number | null, passed = false) => ({
  trade_deadline_week: week,
  current_week: current,
  trade_deadline_passed: passed,
});

test('web and app share one deadline mode block', () => {
  assert.equal(shared('src/lib/deadlineMode.ts'), shared('../web-next/src/lib/deadlineMode.ts'));
});

test('state: none without a real deadline, closed after it, open before it', () => {
  assert.deepEqual(deadlineState(null), { phase: 'none' });
  assert.deepEqual(deadlineState(win(null, 5)), { phase: 'none' });
  assert.deepEqual(deadlineState(win(11, 12, true)), { phase: 'closed' });
  assert.deepEqual(deadlineState(win(11, 9)), { phase: 'open', deadlineWeek: 11, weeksLeft: 2 });
  assert.deepEqual(deadlineState(win(11, 11)), { phase: 'open', deadlineWeek: 11, weeksLeft: 0 });
  assert.deepEqual(deadlineState(win(11, null)), { phase: 'open', deadlineWeek: 11, weeksLeft: null });
});

test('posture: competing buys, rebuilding sells, everything else is balanced', () => {
  assert.equal(deadlinePosture('contender'), 'buy');
  assert.equal(deadlinePosture('fringe_contender'), 'buy');
  assert.equal(deadlinePosture('rebuild'), 'sell');
  assert.equal(deadlinePosture('tank'), 'sell');
  assert.equal(deadlinePosture('retool'), 'balanced');
  assert.equal(deadlinePosture(undefined), 'balanced');
});

test('copy names the weeks left and the buy/sell action', () => {
  const two = deadlineState(win(11, 9));
  assert.equal(deadlineCopy(two, 'sell')?.headline, 'Deadline in 2 weeks: sell aging depth');
  assert.equal(deadlineCopy(two, 'buy')?.headline, 'Deadline in 2 weeks: buy a starter');
  assert.equal(deadlineCopy(deadlineState(win(11, 10)), 'buy')?.headline, 'Deadline in 1 week: buy a starter');
  const last = deadlineCopy(deadlineState(win(11, 11)), 'sell');
  assert.equal(last?.headline, 'Last call, deadline is this week: sell aging depth');
  assert.equal(last?.urgent, true);
  assert.equal(deadlineCopy(deadlineState(win(11, null)), 'balanced')?.headline, 'Deadline is Week 11: review your trade ideas');
});

test('no copy once trades are closed or when there is no deadline', () => {
  assert.equal(deadlineCopy(deadlineState(win(11, 12, true)), 'buy'), null);
  assert.equal(deadlineCopy(deadlineState(win(null, 3)), 'buy'), null);
  assert.match(DEADLINE_CLOSED_COPY, /closed/);
});

test('dashboard card appears only in the last two weeks', () => {
  assert.equal(showDeadlineCard(deadlineState(win(11, 8))), false);
  assert.equal(showDeadlineCard(deadlineState(win(11, 9))), true);
  assert.equal(showDeadlineCard(deadlineState(win(11, 11))), true);
  assert.equal(showDeadlineCard(deadlineState(win(11, null))), false);
  assert.equal(showDeadlineCard(deadlineState(win(11, 12, true))), false);
});

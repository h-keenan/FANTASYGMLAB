// Run with: node --experimental-strip-types --test src/lib/simTo.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import type { SimToWeek } from './simGame.ts';
import { simToCanForce, simToFixLabel, simToFixTab, simToHeadline, simToProgressLabel, simToRecordLine, simToWeekLine } from './simTo.ts';

const wk = (week: number, over: Partial<SimToWeek> = {}): SimToWeek => ({ week, kind: 'regular', result: 'w', your_pts: 112.4, opp_pts: 98.66, opponent: 'Rats', auto_filled: [], ...over });

test('headline names the weeks', () => {
  assert.equal(simToHeadline(0, null), 'Nothing simulated');
  assert.equal(simToHeadline(1, { weeks: [wk(3)] }), 'Simmed Week 3');
  assert.equal(simToHeadline(4, { weeks: [wk(3), wk(4), wk(5), wk(6)] }), 'Simmed 4 weeks (Weeks 3-6)');
  assert.equal(simToHeadline(2, { weeks: [wk(15, { kind: 'playoff' }), wk(16, { kind: 'playoff' })] }), 'Played 2 playoff rounds');
});

test('week lines and record line', () => {
  assert.equal(simToWeekLine(wk(3)), 'W 112.4-98.7 vs Rats');
  assert.equal(simToWeekLine(wk(4, { result: 'bye' })), 'Bye week');
  assert.equal(simToRecordLine({ record: { before: '2-1', after: '4-2' }, rank: { before: 4, after: 2 } }), '2-1 to 4-2 · #4 to #2');
});

test('fix buttons, forcing and tabs follow the stop', () => {
  assert.equal(simToFixLabel({ fix: 'lineup', code: 'starter_out' }), 'Fix lineup');
  assert.equal(simToFixLabel({ fix: 'roster', code: 'roster_over_limit' }), 'Make cuts');
  assert.equal(simToFixLabel({ fix: null, code: 'time_budget' }), null);
  assert.equal(simToCanForce({ code: 'trade_offers' }), true);
  assert.equal(simToCanForce({ code: 'roster_over_limit' }), false);
  assert.deepEqual([simToFixTab({ fix: 'lineup' }), simToFixTab({ fix: 'inbox' }), simToFixTab({ fix: 'premium' })], ['team', 'trades', null]);
  assert.equal(simToProgressLabel('Trade deadline (week 10)'), 'Simulating: trade deadline (week 10)...');
});

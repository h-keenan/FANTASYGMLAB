// Run with: node --experimental-strip-types --test src/lib/thisWeek.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { hasThisWeekContent, thisWeekTarget, thisWeekTitle, thisWeekToneKey } from './thisWeek.ts';

test('CTAs open the screen for the move, never a lineup editor', () => {
  assert.deepEqual(thisWeekTarget('matchup', 'l1', 'L'), { name: 'Matchup', params: { leagueId: 'l1', leagueName: 'L' } });
  assert.equal(thisWeekTarget('trade_hub', 'l1', 'L').name, 'Trades');
  assert.equal(thisWeekTarget('waivers', 'l1', 'L').name, 'Waivers');
  assert.equal(thisWeekTarget('live_draft', 'l1', 'L').name, 'DraftCenter');
  assert.deepEqual(thisWeekTarget('connect_league', 'l1', 'L'), { name: 'Home', params: { openAddLeague: true } });
});

test('tone keys use the fixed semantic colors', () => {
  assert.equal(thisWeekToneKey('positive'), 'success');
  assert.equal(thisWeekToneKey('risk'), 'danger');
  assert.equal(thisWeekToneKey('trade'), 'accent');
  assert.equal(thisWeekToneKey('neutral'), 'textTertiary');
});

test('title carries the week; empty payloads render nothing', () => {
  assert.equal(thisWeekTitle({ mode: 'in_season', week: 7, rows: [], next_action: null }), 'This week · Week 7');
  assert.equal(thisWeekTitle({ mode: 'next_action', week: null, rows: [], next_action: null }), 'This week');
  assert.equal(hasThisWeekContent(null), false);
  assert.equal(hasThisWeekContent({ mode: 'in_season', week: 1, rows: [], next_action: null }), false);
  assert.equal(
    hasThisWeekContent({
      mode: 'next_action',
      week: null,
      rows: [],
      next_action: { headline: 'h', why: 'w', cta_label: 'c', route: 'draft_center' },
    }),
    true,
  );
});

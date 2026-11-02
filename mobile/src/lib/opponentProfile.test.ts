// Run with: node --experimental-strip-types --test src/lib/opponentProfile.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { firstsFlowText, hasProfileContent, offerCaption, ordinal, picksText, rankText } from './opponentProfile.ts';

test('ordinals handle teens', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd']);
});

test('rank and pick text', () => {
  assert.equal(rankText({ position: 'RB', rank: 1, of: 12 }), 'RB, 1st of 12');
  assert.equal(
    picksText({ rank: 2, of: 12, pick_count: 7, first_rounders: 1, firsts_acquired: 0, firsts_sent: 0 }),
    '2nd of 12 in draft capital · 7 picks · 1 first',
  );
});

test('first flow hidden when nothing moved', () => {
  assert.equal(firstsFlowText({ rank: 1, of: 12, pick_count: 1, first_rounders: 1, firsts_acquired: 0, firsts_sent: 0 }), null);
  assert.equal(
    firstsFlowText({ rank: 1, of: 12, pick_count: 1, first_rounders: 1, firsts_acquired: 2, firsts_sent: 1 }),
    'Firsts: 2 acquired, 1 traded away',
  );
});

test('offer caption by side', () => {
  assert.match(offerCaption({ player_id: '1', name: 'A B', position: 'RB', team: 'KC', side: 'receive' }), /asking for A B/);
  assert.match(offerCaption({ player_id: '1', name: 'A B', position: 'RB', team: 'KC', side: 'send' }), /offering A B/);
});

test('no content for failed or not-ready', () => {
  assert.equal(hasProfileContent(null), false);
  assert.equal(hasProfileContent({ ok: true, reason: 'no_rankings_data', roster_id: '2' }), false);
});

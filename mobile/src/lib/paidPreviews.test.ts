import { test } from 'node:test';
import assert from 'node:assert/strict';

import { paidPreview } from './paidPreviews.ts';
import { paidPreview as webPaidPreview } from '../../../web-next/src/lib/paidPreviews.ts';

const KEYS = [
  'draft_center',
  'live_draft',
  'commissioner',
  'college_scouting',
  'portfolio',
  'exposure',
  'gm_plan',
  'playoff_odds',
  'what_if',
  'trade_finder',
];

test('every gated surface has a preview and the app copy matches the web copy', () => {
  for (const key of KEYS) {
    const preview = paidPreview(key, 'Test League');
    assert.ok(preview && preview.bullets.length > 0, key);
    assert.deepEqual(preview, webPaidPreview(key, 'Test League'), key);
  }
});

test('names the league and falls back to a neutral phrase', () => {
  assert.ok(paidPreview('draft_center', 'No quitters league')?.bullets.some((b) => b.includes('No quitters league')));
  assert.ok(paidPreview('draft_center')?.bullets.some((b) => b.includes('your league')));
  assert.equal(paidPreview('saved_leagues'), null);
});

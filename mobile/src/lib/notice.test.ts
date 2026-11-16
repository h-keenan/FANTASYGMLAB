// Run with: node --experimental-strip-types --test src/lib/notice.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { NOTICE_MS, noticeText, noticeToneFor } from './notice.ts';

test('noticeText joins title and detail into one sentence-cased line', () => {
  assert.equal(noticeText('Could not update Watchlist', 'Please try again in a moment.'), 'Could not update Watchlist. Please try again in a moment.');
  assert.equal(noticeText('Test notification sent.'), 'Test notification sent');
});

test('noticeToneFor reads the legacy alert titles', () => {
  assert.equal(noticeToneFor('Could not rename league'), 'error');
  assert.equal(noticeToneFor('Watchlist is full'), 'error');
  assert.equal(noticeToneFor('Test notification sent'), 'success');
  assert.equal(noticeToneFor('Select a league first'), 'info');
});

test('errors stay longest', () => {
  assert.ok(NOTICE_MS.error > NOTICE_MS.info && NOTICE_MS.info > NOTICE_MS.success);
});

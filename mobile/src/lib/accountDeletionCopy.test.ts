import assert from 'node:assert/strict';
import { test } from 'node:test';

import * as copy from './accountDeletionCopy.ts';

test('App Store notice points to iOS Settings Subscriptions and links there', () => {
  assert.match(copy.DELETE_ACCOUNT_APP_STORE_NOTE, /iOS Settings/);
  assert.match(copy.APP_STORE_SUBSCRIPTIONS_URL, /apps\.apple\.com\/account\/subscriptions$/);
});

test('deletion copy has no em-dashes', () => {
  for (const v of Object.values(copy)) assert.ok(!String(v).includes('—'));
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { parseReferralCode } from './referralCode.ts';

test('parses and sanitizes a ref code', () => {
  assert.equal(parseReferralCode('fantasygmlab://?ref=ABC123'), 'ABC123');
  assert.equal(parseReferralCode('https://app.fantasygmlab.com/?utm_source=x&ref=Zz_9-1#top'), 'Zz_9-1');
  assert.equal(parseReferralCode('https://x.com/?ref=a%20b<c>'), 'abc');
  assert.equal(parseReferralCode('https://x.com/?other=1'), '');
  assert.equal(parseReferralCode(null), '');
});

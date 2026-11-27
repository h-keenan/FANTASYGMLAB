import assert from 'node:assert/strict';
import { test } from 'node:test';

import { tryTabFromUrl } from './tryDeepLink.ts';

test('tryTabFromUrl: supported topics open the matching sample tab', () => {
  assert.equal(tryTabFromUrl('fantasygmlab://try/trade'), 'trade');
  assert.equal(tryTabFromUrl('fantasygmlab://try/start-sit'), 'game_plan');
  assert.equal(tryTabFromUrl('fantasygmlab:///try/waivers/?utm_source=ad_app&utm_campaign=x'), 'game_plan');
});

test('tryTabFromUrl: topics with no app demo, unknown topics and other links are not claimed', () => {
  assert.equal(tryTabFromUrl('fantasygmlab://try/playoffs'), null);
  assert.equal(tryTabFromUrl('fantasygmlab://try/dynasty-values'), null);
  assert.equal(tryTabFromUrl('fantasygmlab://try/nope'), null);
  assert.equal(tryTabFromUrl('fantasygmlab://try'), null);
  assert.equal(tryTabFromUrl('fantasygmlab://gm-game?quickstart=1'), null);
  assert.equal(tryTabFromUrl('fantasygmlab://try/trade/extra'), null);
  assert.equal(tryTabFromUrl(null), null);
});

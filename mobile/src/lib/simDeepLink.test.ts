import test from 'node:test';
import assert from 'node:assert/strict';

import { isSimQuickStartUrl } from './simDeepLink.ts';

test('isSimQuickStartUrl: only gm-game with quickstart=1', () => {
  assert.equal(isSimQuickStartUrl('fantasygmlab://gm-game?quickstart=1'), true);
  assert.equal(isSimQuickStartUrl('fantasygmlab:///gm-game/?utm=ad&quickstart=1'), true);
  assert.equal(isSimQuickStartUrl('fantasygmlab://gm-game'), false);
  assert.equal(isSimQuickStartUrl('fantasygmlab://gm-game?quickstart=0'), false);
  assert.equal(isSimQuickStartUrl('fantasygmlab://home?quickstart=1'), false);
  assert.equal(isSimQuickStartUrl(null), false);
});

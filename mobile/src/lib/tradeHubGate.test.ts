import assert from 'node:assert/strict';
import { test } from 'node:test';

import { TRADE_HUB_UPGRADE_LABEL, tradeHubGateBody, tradeHubGateTitle } from './tradeHubGate.ts';

test('the gate title counts the hidden ideas on this board', () => {
  assert.equal(tradeHubGateTitle(1), '1 more trade idea on this board');
  assert.equal(tradeHubGateTitle(3), '3 more trade ideas on this board');
});

test('the gate body says Pro unlocks the board, and mentions an ad only when one can run', () => {
  assert.equal(tradeHubGateBody(2, null), 'Free shows the top 2. Go Pro to unlock the full board.');
  assert.match(tradeHubGateBody(2, 3), /Watch a quick ad to reveal 3 more/);
  assert.equal(TRADE_HUB_UPGRADE_LABEL, 'Upgrade to Pro');
});

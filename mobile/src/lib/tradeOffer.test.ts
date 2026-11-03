import assert from 'node:assert/strict';
import test from 'node:test';

import { canBuildOffer, offerPrefillFrom, offerPrefillKey, resolvePrefill } from './tradeOffer.ts';

const ownership = { myPlayerIds: new Set(['mine']), rosteredPlayerIds: new Set(['mine', 'theirs']) };

test('Build an offer is only for a player on another roster', () => {
  assert.equal(canBuildOffer('theirs', ownership), true);
  assert.equal(canBuildOffer('mine', ownership), false);
  assert.equal(canBuildOffer('free-agent', ownership), false);
  assert.equal(canBuildOffer('theirs', null), false);
  assert.equal(canBuildOffer('', ownership), false);
});

test('an offer becomes id-only Analyzer prefill', () => {
  const prefill = offerPrefillFrom({
    send: [
      { kind: 'player', id: 'p1' },
      { kind: 'pick', id: '2027:2:4' },
    ],
    receive: [{ kind: 'player', id: 't1' }],
  });
  assert.deepEqual(prefill, { send: ['p1'], receive: ['t1'], sendPicks: ['2027:2:4'], receivePicks: [] });
  assert.equal(offerPrefillKey(prefill), 'p1|t1|2027:2:4|');
});

test('prefill drops ids that are not in this league instead of inventing them', () => {
  const resolved = resolvePrefill(
    { send: ['p1', 'gone'], receive: ['t1'], sendPicks: ['2027:2:4'], receivePicks: ['2099:9:9'] },
    [{ player_id: 'p1' }, { player_id: 't1' }],
    [{ pick_id: '2027:2:4' }],
  );
  assert.deepEqual(resolved.send, [{ player_id: 'p1' }]);
  assert.deepEqual(resolved.receive, [{ player_id: 't1' }]);
  assert.deepEqual(resolved.sendPicks, [{ pick_id: '2027:2:4' }]);
  assert.deepEqual(resolved.receivePicks, []);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { isOnWaiverList, listRowIndex, locateWaiverPlayer, type WaiverLists } from './waiverHighlight.ts';

const lists = (over: Partial<WaiverLists> = {}): WaiverLists => ({
  priorityAdds: [{ player_id: 'p1' }],
  stashCandidates: [{ player_id: 's1' }],
  watchlistCandidates: [{ player_id: 'w1' }],
  faabTargets: [{ player_id: 'f1' }],
  players: [{ player_id: 'p1' }, { player_id: 'x1' }],
  idpPlayers: [{ player_id: 'd1', position: 'LB' }],
  isPremium: true,
  ...over,
});

test('priority add opens recommended', () => {
  assert.deepEqual(locateWaiverPlayer('p1', lists()), { found: true, tab: 'recommended', position: 'ALL' });
});
test('stash opens recommended only when premium', () => {
  assert.equal(locateWaiverPlayer('s1', lists()).found && (locateWaiverPlayer('s1', lists()) as any).tab, 'recommended');
  assert.equal(locateWaiverPlayer('s1', lists({ isPremium: false })).found, false);
});
test('plain free agent opens explore', () => {
  assert.deepEqual(locateWaiverPlayer('x1', lists()), { found: true, tab: 'explore', position: 'ALL' });
});
test('idp player sets position filter', () => {
  assert.deepEqual(locateWaiverPlayer('d1', lists()), { found: true, tab: 'explore', position: 'LB' });
});
test('missing, empty and null ids are not found', () => {
  assert.equal(locateWaiverPlayer('zzz', lists()).found, false);
  assert.equal(locateWaiverPlayer('', lists()).found, false);
  assert.equal(locateWaiverPlayer(null, lists()).found, false);
  assert.equal(isOnWaiverList('x1', lists()), true);
});
test('listRowIndex divides by columns', () => {
  assert.equal(listRowIndex(5, 2), 2);
  assert.equal(listRowIndex(5, 1), 5);
  assert.equal(listRowIndex(5, 0), 5);
});

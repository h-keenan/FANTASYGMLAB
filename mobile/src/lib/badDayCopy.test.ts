import assert from 'node:assert/strict';
import { test } from 'node:test';

import { asOfLabel, classifyErrorMessage, friendlyStatusMessage, SERVER_ERROR_MESSAGE, SERVICE_BUSY_MESSAGE, staleNote } from './badDayCopy.ts';
import { looksOffline, isOffline, reportRequestOutcome, resetConnectivityForTests, subscribeConnectivity } from './connectivity.ts';

test('a bare 5xx status becomes a sentence, a server detail is kept', () => {
  assert.equal(friendlyStatusMessage(500, ''), SERVER_ERROR_MESSAGE);
  assert.equal(friendlyStatusMessage(502, 'Request failed (502).'), SERVER_ERROR_MESSAGE);
  assert.equal(friendlyStatusMessage(503, ''), SERVICE_BUSY_MESSAGE);
  assert.equal(friendlyStatusMessage(500, 'Roster sync is down.'), 'Roster sync is down.');
  assert.equal(friendlyStatusMessage(401, ''), 'Not signed in.');
  assert.match(friendlyStatusMessage(409, ''), /^Request failed with status 409/);
});

test('error messages classify into the bad days with their own next step', () => {
  assert.equal(classifyErrorMessage('Not signed in.'), 'session');
  assert.equal(classifyErrorMessage('League not found.'), 'league_gone');
  assert.equal(classifyErrorMessage("Couldn't connect, check your connection and try again."), 'offline');
  assert.equal(classifyErrorMessage(SERVER_ERROR_MESSAGE), 'server');
  assert.equal(classifyErrorMessage('Roster not found in this league.'), 'other');
});

test('as-of note is quiet when fresh and online, shown when stale or offline', () => {
  const now = new Date('2026-11-17T15:42:00').getTime();
  assert.equal(staleNote(now - 60_000, { now }), '');
  assert.match(staleNote(now - 60_000, { now, offline: true }), /^As of /);
  assert.match(staleNote(now - 3_600_000, { now }), /^As of /);
  assert.equal(asOfLabel(0), '');
  assert.match(asOfLabel(now - 3 * 86_400_000, now), /^As of \w{3} /);
});

test('connectivity: a transport failure raises offline, a timeout does not change it, any response clears it', () => {
  resetConnectivityForTests();
  const seen: boolean[] = [];
  subscribeConnectivity((o) => seen.push(o));
  reportRequestOutcome({ error: new Error('Network request failed') });
  assert.equal(isOffline(), true);
  reportRequestOutcome({ error: Object.assign(new Error('x'), { name: 'AbortError' }) });
  assert.equal(isOffline(), true);
  reportRequestOutcome({ responded: true });
  assert.equal(isOffline(), false);
  assert.deepEqual(seen, [true, false]);
  assert.equal(looksOffline(new Error('request timed out')), false);
  assert.equal(looksOffline(new TypeError('Cannot read properties of undefined')), false);
  resetConnectivityForTests();
});

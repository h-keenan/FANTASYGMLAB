import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  parseLiveActivitiesFlag,
  planLiveActivityAction,
  toContentState,
  toWidgetSnapshot,
  type LiveSnapshotInput,
} from './liveActivityCore.ts';

const live: LiveSnapshotInput = {
  available: true,
  should_run: true,
  week: 8,
  game_state: 'live',
  me: { team_name: 'Me', points: 71.5 },
  opponent: { team_name: 'Them', points: 64 },
  margin: 7.5,
  win_probability: 0.62,
};
const on = { enabled: true, isGuest: false };

test('flag defaults off', () => {
  assert.equal(parseLiveActivitiesFlag(undefined), false);
  assert.equal(parseLiveActivitiesFlag(''), false);
  assert.equal(parseLiveActivitiesFlag('1'), true);
});

test('content state maps real points and refuses fabricated ones', () => {
  assert.equal(toContentState(live)?.myPoints, 71.5);
  assert.equal(toContentState({ ...live, me: { team_name: 'Me', points: null } }), null);
  assert.equal(toContentState({ ...live, available: false }), null);
});

test('action plan: start, update, end, none', () => {
  assert.equal(planLiveActivityAction(live, false, on), 'start');
  assert.equal(planLiveActivityAction(live, true, on), 'update');
  assert.equal(planLiveActivityAction({ ...live, should_run: false, game_state: 'final' }, true, on), 'end');
  assert.equal(planLiveActivityAction({ ...live, should_run: false }, false, on), 'none');
  assert.equal(planLiveActivityAction(null, true, on), 'end');
});

test('flag off or guest never starts, and ends anything running', () => {
  assert.equal(planLiveActivityAction(live, false, { enabled: false, isGuest: false }), 'none');
  assert.equal(planLiveActivityAction(live, false, { enabled: true, isGuest: true }), 'none');
  assert.equal(planLiveActivityAction(live, true, { enabled: false, isGuest: false }), 'end');
});

test('widget snapshot puts unread first, caps, drops empty titles', () => {
  const snap = toWidgetSnapshot(
    'L',
    [
      { title: 'old', matched_player: null, read: true },
      { title: '  ', matched_player: null, read: false },
      { title: 'new1', matched_player: 'A', read: false },
      { title: 'new2', matched_player: null, read: false },
      { title: 'new3', matched_player: null, read: false },
    ],
    5,
    3,
  );
  assert.deepEqual(snap.alerts.map((a) => a.title), ['new1', 'new2', 'new3']);
  assert.equal(snap.unreadCount, 3);
});

test('Swift ContentState fields match the TS content state', () => {
  const dir = join(process.cwd(), 'native', 'live-activity') + '/'; // npm test runs from mobile/
  const keys = Object.keys(toContentState(live)!).sort();
  for (const file of ['widgets/FantasyDeskActivityAttributes.swift']) {
    const src = readFileSync(dir + file, 'utf8');
    const block = src.slice(src.indexOf('struct ContentState'));
    const fields = [...block.matchAll(/var (\w+):/g)].map((m) => m[1]).sort();
    assert.deepEqual(fields, keys, file);
  }
});

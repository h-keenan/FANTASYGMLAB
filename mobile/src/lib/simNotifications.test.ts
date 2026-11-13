// Run with: node --experimental-strip-types --test src/lib/simNotifications.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simNotifBadge, simNotifGroups, simNotifKey, simNotifMarkAllRead, simNotifParseCursor, simNotifTargetTab, simNotifTime, simNotifUnread, type SimNotification } from './simNotifications.ts';

const n = (seq: number, week: number): SimNotification => ({ id: `k:${seq}`, seq, week, kind: 'k', icon: 'trade', headline: `h${seq}`, target: { screen: 'home' } });

test('unread against the read cursor, mark-all-read, badge', () => {
  const items = [n(30, 3), n(20, 2), n(10, 1)];
  assert.equal(simNotifUnread(items, 0), 3);
  assert.equal(simNotifUnread(items, 20), 1);
  assert.equal(simNotifMarkAllRead(40, 30), 40);
  assert.equal(simNotifParseCursor('junk'), 0);
  assert.equal(simNotifBadge(12), '9+');
  assert.equal(simNotifBadge(0), '');
});

test('groups by week newest first, deep links, refetch key', () => {
  const groups = simNotifGroups([n(10, 1), n(31, 3), n(30, 3), n(5, 0)]);
  assert.deepEqual(groups.map((g) => g.label), ['Week 3', 'Week 1', 'Draft']);
  assert.deepEqual(groups[0].items.map((i) => i.seq), [31, 30]);
  assert.equal(simNotifTime({ week: 7 }), 'Wk 7');
  assert.equal(simNotifTargetTab({ screen: 'draft' }), 'home');
  assert.equal(simNotifTargetTab({ screen: 'trades' }), 'trades');
  const g = { status: 'in_season', week: 4, pending: { inbox: 2, lineup_warnings: 1, claims: 0 } };
  assert.equal(simNotifKey(g), simNotifKey({ ...g }));
  assert.notEqual(simNotifKey(g), simNotifKey({ ...g, week: 5 }));
});

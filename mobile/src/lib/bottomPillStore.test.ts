import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

import { getPillState, resetPillStore, setPillBarPresent, setPillContext, subscribePill } from './bottomPillStore.ts';
import { normalizePillContext, pillMode, PILL_MAX_TABS } from './bottomNav.ts';

const ctx = (over = {}) => ({ id: 'team', label: 'Team', tabs: [{ key: 'a', label: 'A' }], activeKey: 'a', onSelect: () => {}, ...over });
beforeEach(resetPillStore);

test('publishes only when what is shown changes, and keeps callbacks fresh', () => {
  let n = 0;
  subscribePill(() => n++);
  const who = {};
  let first = 0;
  let second = 0;
  setPillContext(who, ctx({ onSelect: () => first++ }));
  setPillContext(who, ctx({ onSelect: () => second++ }));
  assert.equal(n, 1);
  getPillState().ctx?.onSelect('a');
  assert.equal(first, 0);
  assert.equal(second, 1);
  setPillContext(who, ctx({ activeKey: 'b', tabs: [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }] }));
  assert.equal(n, 2);
});

test('only the owner may clear; bar-present is tracked', () => {
  const a = {};
  const b = {};
  setPillContext(a, ctx());
  setPillContext(b, ctx({ id: 'trades' }));
  setPillContext(a, null);
  assert.equal(getPillState().ctx?.id, 'trades');
  setPillContext(b, null);
  assert.equal(getPillState().ctx, null);
  setPillBarPresent(true);
  assert.equal(getPillState().barPresent, true);
});

test('normalize caps tabs and modes follow context + menu', () => {
  const many = Array.from({ length: 9 }, (_, i) => ({ key: `k${i}`, label: `L${i}` }));
  assert.equal(normalizePillContext(ctx({ tabs: many }))?.tabs.length, PILL_MAX_TABS);
  assert.equal(normalizePillContext(null), null);
  assert.equal(pillMode(false, true), 'global');
  assert.equal(pillMode(true, true), 'menu');
  assert.equal(pillMode(true, false), 'context');
});

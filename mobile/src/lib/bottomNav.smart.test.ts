import assert from 'node:assert/strict';
import { test } from 'node:test';

import { pillOrbBadge, simPillPlan, type PillContext } from './bottomNav.ts';

const ctx = (over: Partial<PillContext>): PillContext => ({ id: 'x', label: 'x', tabs: [], activeKey: '', onSelect: () => {}, ...over });
const auto = { key: 'auto-set', label: 'Auto-set', onPress: () => {} };
const tabs = [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }];

test('plain in-season page: orb | Sim to | Advance', () => {
  assert.deepEqual(simPillPlan({ context: null, simToAvailable: true }), { segment: null, inlineAction: null, simTo: true, advance: true });
});
test('a page action takes the Sim to slot and keeps Advance', () => {
  const p = simPillPlan({ context: ctx({ primary: auto }), simToAvailable: true });
  assert.equal(p.inlineAction?.key, 'auto-set');
  assert.equal(p.simTo, false);
  assert.equal(p.advance, true);
});
test('a disabled page action is hidden and Sim to returns', () => {
  const p = simPillPlan({ context: ctx({ primary: { ...auto, disabled: true } }), simToAvailable: true });
  assert.equal(p.inlineAction, null);
  assert.equal(p.simTo, true);
});
test('tabs (the draft room) own the pill: no Advance, no Sim to', () => {
  const p = simPillPlan({ context: ctx({ tabs, activeKey: 'a', primary: auto }), simToAvailable: true });
  assert.equal(p.segment?.tabs.length, 2);
  assert.equal(p.advance, false);
  assert.equal(p.simTo, false);
});
test('paywalled or no sim-to: never Sim to', () => {
  assert.equal(simPillPlan({ context: null, simToAvailable: true, paywalled: true }).simTo, false);
  assert.equal(simPillPlan({ context: null, simToAvailable: false }).simTo, false);
});
test('orb badge sums the global tab counts', () => {
  assert.equal(pillOrbBadge([{ badge: 2 }, { badge: 0 }, {}, { badge: 3 }]), 5);
});

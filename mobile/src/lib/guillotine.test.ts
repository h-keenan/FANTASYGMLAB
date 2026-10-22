import test from 'node:test';
import assert from 'node:assert/strict';

import { guillotineView } from './guillotine.ts';

const base = {
  ok: true,
  is_guillotine: true,
  reason: '',
  alive: true,
  weeks_survived: 4,
  teams_alive: 9,
  teams_total: 12,
  chop_line: null,
};

test('renders nothing for normal leagues or missing data', () => {
  assert.equal(guillotineView(null), null);
  assert.equal(guillotineView({ ...base, is_guillotine: false }), null);
});

test('says nothing about the chop line without projections', () => {
  const view = guillotineView(base)!;
  assert.deepEqual(view.badge, { label: 'Alive', tone: 'success' });
  assert.deepEqual(view.items.map((i) => i.label), ['Survived', 'Alive']);
});

test('flags at-risk with the margin', () => {
  const view = guillotineView({
    ...base,
    chop_line: { line: 88.4, my_projected: 85.1, margin: -3.3, at_risk: true },
  })!;
  assert.deepEqual(view.badge, { label: 'At risk', tone: 'danger' });
  assert.deepEqual(view.items[view.items.length - 1], { label: 'Margin', value: '-3.3', tone: 'risk' });
});

test('marks eliminated teams and hides the chop line', () => {
  const view = guillotineView({
    ...base,
    alive: false,
    chop_line: { line: 90, my_projected: null, margin: null, at_risk: false },
  })!;
  assert.equal(view.badge.label, 'Chopped');
  assert.equal(view.items.length, 2);
});

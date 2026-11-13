// Run with: node --experimental-strip-types --test src/lib/tradeSheetPicker.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  EMPTY_FILTERS,
  applyLabel,
  conditionsFor,
  filterSheetItems,
  initialSheetState,
  itemKey,
  selectedItems,
  sheetReducer,
  summarizeItems,
  type SheetAction,
  type SheetItem,
  type SheetState,
} from './tradeSheetPicker.ts';

const player = (id: string, over: Partial<SheetItem> = {}): SheetItem => ({ key: itemKey('player', id), kind: 'player', id, label: `P${id}`, position: 'RB', team: 'KC', age: 25, value: 100, conditions: ['healthy'], ...over });
const pick = (id: string): SheetItem => ({ key: itemKey('pick', id), kind: 'pick', id, label: `K${id}`, position: null, team: null, age: null, value: 50, conditions: [] });
const run = (state: SheetState, ...actions: SheetAction[]) => actions.reduce(sheetReducer, state);

test('conditions', () => {
  assert.deepEqual(conditionsFor({ injuryStatus: 'Out', age: 21 }), ['injured', 'rookie']);
  assert.deepEqual(conditionsFor({ age: 27 }), ['healthy']);
  assert.deepEqual(conditionsFor({ status: 'Bye', age: 27 }), ['bye']);
});

test('filters OR within a group, AND across groups, and keep picks out of player filters', () => {
  const items = [player('1', { position: 'RB' }), player('2', { position: 'WR', conditions: ['injured'] }), player('3', { position: 'WR' }), pick('a')];
  const base = { tab: 'players' as const, query: '', filters: EMPTY_FILTERS };
  assert.deepEqual(filterSheetItems(items, { ...base, filters: { positions: ['WR'], conditions: ['injured'] } }).map((i) => i.id), ['2']);
  assert.deepEqual(filterSheetItems(items, { ...base, tab: 'picks', filters: { positions: ['QB'], conditions: [] } }).map((i) => i.id), ['a']);
});

test('selection toggles, caps at max, filters stay draft until Apply', () => {
  let s = run(initialSheetState(), { type: 'toggle', key: 'a', max: 2 }, { type: 'toggle', key: 'b', max: 2 }, { type: 'toggle', key: 'c', max: 2 });
  assert.deepEqual(s.selected, ['a', 'b']);
  s = run(initialSheetState(), { type: 'openFilters' }, { type: 'draftPosition', position: 'RB' });
  assert.deepEqual(s.filters, EMPTY_FILTERS);
  s = run(s, { type: 'applyFilters' });
  assert.deepEqual(s.filters.positions, ['RB']);
  s = run(s, { type: 'openFilters' }, { type: 'draftPosition', position: 'WR' }, { type: 'closeFilters' });
  assert.deepEqual(s.filters.positions, ['RB']);
});

test('summaries and footer label', () => {
  const chosen = selectedItems([player('1'), pick('a')], ['pick:a', 'player:9', 'player:1']);
  assert.deepEqual(summarizeItems(chosen), { count: 2, players: 1, picks: 1, total: 150 });
  assert.equal(applyLabel(['a', 'b'], []), 'Add 2 to trade');
  assert.equal(applyLabel(['a'], ['a']), 'Done');
});

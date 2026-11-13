// Run with: node --experimental-strip-types --test src/lib/filterSheet.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  activeFilterChips,
  activeFilterCount,
  applyButtonLabel,
  isChipSelected,
  removeFilterChip,
  singleValue,
  toggleFilterValue,
  valuesFromSingles,
  type FilterGroup,
} from './filterSheet.ts';

const pos: FilterGroup = { id: 'pos', label: 'Position', anyValue: 'ALL', options: [{ value: 'ALL', label: 'Any' }, { value: 'QB', label: 'QB' }, { value: 'RB', label: 'RB' }] };
const tags: FilterGroup = { id: 'tags', label: 'Tags', multi: true, options: [{ value: 'a', label: 'Alpha' }, { value: 'b', label: 'Beta' }] };

test('counts real filters only', () => {
  assert.equal(activeFilterCount([pos, tags], { pos: ['ALL'], tags: ['a', 'b'] }), 2);
});

test('single-select replaces / clears; multi-select toggles', () => {
  let v = toggleFilterValue(pos, {}, 'QB');
  v = toggleFilterValue(pos, v, 'RB');
  assert.deepEqual(v.pos, ['RB']);
  assert.deepEqual(toggleFilterValue(pos, v, 'RB').pos, []);
  const t = toggleFilterValue(tags, toggleFilterValue(tags, {}, 'a'), 'b');
  assert.deepEqual(t.tags, ['a', 'b']);
});

test('any chip is selected when nothing else is; chips remove', () => {
  assert.equal(isChipSelected(pos, {}, 'ALL'), true);
  const values = { pos: ['QB'], tags: ['a'] };
  assert.deepEqual(activeFilterChips([pos, tags], values).map((c) => c.label), ['QB', 'Alpha']);
  assert.deepEqual(removeFilterChip(values, { groupId: 'tags', value: 'a' }).tags, []);
});

test('footer label and single-value round trip', () => {
  assert.equal(applyButtonLabel(24), 'Show 24 results');
  assert.equal(applyButtonLabel(0), 'No results');
  assert.equal(singleValue(pos, valuesFromSingles([pos], { pos: 'QB' })), 'QB');
});

// Run with: node --experimental-strip-types --test src/lib/playerNews.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { alsoReportedLine, flattenNewsPages, groupNewsByDay, newsDayLabel, sameStory } from './playerNews.ts';

const NOW = new Date(2026, 9, 28, 15, 0, 0).getTime();
const at = (d: Date) => d.getTime() / 1000;
const item = (title: string, ts: number | null, extra: object = {}) => ({
  title,
  link: `https://x/${title}`,
  source: 'ESPN',
  summary: null,
  published_ts: ts,
  event_type: null,
  speculative: false,
  ...extra,
});

test('day labels: today, yesterday, older date, undated', () => {
  assert.equal(newsDayLabel(at(new Date(2026, 9, 28, 1)), NOW), 'Today');
  assert.equal(newsDayLabel(at(new Date(2026, 9, 27, 23)), NOW), 'Yesterday');
  assert.equal(newsDayLabel(at(new Date(2026, 9, 20, 9)), NOW), 'Tue, Oct 20');
  assert.ok(newsDayLabel(at(new Date(2025, 11, 2, 9)), NOW).includes('2025'));
  assert.equal(newsDayLabel(null, NOW), 'Earlier');
});

test('groups newest-first items by day in order', () => {
  const sections = groupNewsByDay(
    [item('a', at(new Date(2026, 9, 28, 9))), item('b', at(new Date(2026, 9, 28, 2))), item('c', at(new Date(2026, 9, 20)))],
    NOW,
  );
  assert.deepEqual(
    sections.map((s) => [s.label, s.items.map((i) => i.title)]),
    [
      ['Today', ['a', 'b']],
      ['Tue, Oct 20', ['c']],
    ],
  );
});

test('flattenNewsPages drops stories already shown', () => {
  const merged = flattenNewsPages([{ items: [item('a', 1), item('b', 2)] }, { items: [item('b', 2), item('c', 3)] }]);
  assert.deepEqual(merged.map((i) => i.title), ['a', 'b', 'c']);
});

test('sameStory and alsoReportedLine', () => {
  assert.equal(sameStory(item('a', 1), item('a', 2)), true);
  assert.equal(sameStory(item('a', 1), null), false);
  assert.equal(alsoReportedLine(item('a', 1)), '');
  assert.equal(
    alsoReportedLine(item('a', 1, { also_reported_by: [{ source: 'RotoWire', link: null }, { source: 'CBS Sports', link: null }] })),
    'Also reported by RotoWire, CBS Sports',
  );
});

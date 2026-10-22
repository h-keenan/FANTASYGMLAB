// Run with: node --experimental-strip-types --test src/lib/playerSearch.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { matchPlayersByName } from './playerSearch.ts';

const pool = [
  { name: 'Ja\'Marr Chase' },
  { name: 'Travis Kelce' },
  { name: 'Kenneth Walker III' },
  { name: 'Mike Evans' },
  { name: null },
  { name: 'Ken Mackel' },
];

const names = (rows: Array<{ name: string | null }>) => rows.map((p) => p.name);

test('needs at least two characters', () => {
  assert.deepEqual(matchPlayersByName(pool, ''), []);
  assert.deepEqual(matchPlayersByName(pool, ' k '), []);
});

test('name prefix first, then word prefix, then mid-word, keeping pool order', () => {
  assert.deepEqual(names(matchPlayersByName(pool, 'ke')), ['Kenneth Walker III', 'Ken Mackel', 'Travis Kelce', 'Mike Evans']);
  assert.deepEqual(names(matchPlayersByName(pool, 'kel')), ['Travis Kelce', 'Ken Mackel']);
});

test('case-insensitive, trims, skips nameless rows, honours the limit', () => {
  assert.deepEqual(names(matchPlayersByName(pool, '  CHASE ')), ["Ja'Marr Chase"]);
  assert.deepEqual(names(matchPlayersByName(pool, 'e', 10)), []);
  assert.equal(matchPlayersByName(pool, 'ke', 1).length, 1);
});

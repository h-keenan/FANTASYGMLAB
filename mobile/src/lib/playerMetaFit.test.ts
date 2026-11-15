// Run with: node --experimental-strip-types --test src/lib/playerMetaFit.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateMetaWidth, fitMetaParts, type MetaPart } from './playerMetaFit.ts';

const parts: MetaPart[] = [
  { key: 'team', text: 'BAL' },
  { key: 'age', text: 'Age 26' },
  { key: 'bye', text: 'Bye 13' },
  { key: 'proj', text: 'PROJ 17.8' },
];
const keys = (p: MetaPart[]) => p.map((x) => x.key);

test('drops age, then team, then bye; never PROJ', () => {
  assert.deepEqual(keys(fitMetaParts(parts, 400)), ['team', 'age', 'bye', 'proj']);
  assert.deepEqual(keys(fitMetaParts(parts, estimateMetaWidth(parts, 12) - 1)), ['team', 'bye', 'proj']);
  assert.deepEqual(keys(fitMetaParts(parts, 10)), ['proj']);
});
test('a bye that is soon stays', () => {
  const soon = parts.map((p) => (p.key === 'bye' ? { ...p, tone: 'warning' } : p));
  assert.deepEqual(keys(fitMetaParts(soon, 10)), ['bye', 'proj']);
});

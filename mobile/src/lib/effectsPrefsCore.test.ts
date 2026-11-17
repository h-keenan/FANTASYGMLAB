// Run with: node --experimental-strip-types --test src/lib/effectsPrefsCore.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_EFFECTS_PREFS, EFFECTS_PREFS_KEY, createEffectsPrefs, parseEffectsPrefs } from './effectsPrefsCore.ts';

function memory(initial?: string) {
  const data = new Map<string, string>(initial ? [[EFFECTS_PREFS_KEY, initial]] : []);
  return { data, getItem: async (k: string) => data.get(k) ?? null, setItem: async (k: string, v: string) => void data.set(k, v) };
}

test('defaults: haptics on, reduced effects off', () => {
  assert.deepEqual(DEFAULT_EFFECTS_PREFS, { haptics: true, reducedEffects: false });
  assert.deepEqual(parseEffectsPrefs(null), DEFAULT_EFFECTS_PREFS);
  assert.deepEqual(parseEffectsPrefs('not json'), DEFAULT_EFFECTS_PREFS);
  assert.deepEqual(parseEffectsPrefs('{"haptics":false}'), { haptics: false, reducedEffects: false });
  assert.deepEqual(parseEffectsPrefs('{"haptics":"no","reducedEffects":true}'), { haptics: true, reducedEffects: true });
});

test('set persists and notifies; a new store loads it back', async () => {
  const storage = memory();
  const a = createEffectsPrefs(storage);
  let calls = 0;
  a.subscribe(() => void (calls += 1));
  a.set({ haptics: false });
  assert.equal(calls, 1);
  assert.equal(a.get().haptics, false);
  await Promise.resolve();
  const b = createEffectsPrefs(storage);
  await b.load();
  assert.deepEqual(b.get(), { haptics: false, reducedEffects: false });
});

test('a toggle made before the saved value finishes loading wins', async () => {
  const s = createEffectsPrefs(memory('{"haptics":false,"reducedEffects":true}'));
  s.set({ reducedEffects: false });
  await s.load();
  assert.equal(s.get().reducedEffects, false);
});

test('storage failures never throw', async () => {
  const s = createEffectsPrefs({ getItem: async () => { throw new Error('x'); }, setItem: async () => { throw new Error('y'); } });
  await s.load();
  assert.doesNotThrow(() => s.set({ haptics: false }));
  assert.equal(s.get().haptics, false);
});

// Run with: node --experimental-strip-types --test src/lib/motionDrop1Scan.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import { SPRING, HERO_MS, AMBIENT_MS, EASE } from './motion.ts';

const src = path.resolve(import.meta.dirname, '..');
const read = (rel: string) => fs.readFileSync(path.join(src, rel), 'utf8');

function walk(dir: string, out: string[] = []): string[] {
  for (const n of fs.readdirSync(dir)) {
    const f = path.join(dir, n);
    if (fs.statSync(f).isDirectory()) walk(f, out);
    else if (/\.tsx?$/.test(n) && !/\.test\./.test(n)) out.push(f);
  }
  return out;
}

test('only haptic.ts imports expo-haptics', () => {
  const offenders = walk(src).filter((f) => /from\s+['"]expo-haptics['"]/.test(fs.readFileSync(f, 'utf8')) && !f.endsWith(path.join('lib', 'haptic.ts')));
  assert.deepEqual(offenders, []);
  assert.ok(!fs.existsSync(path.join(src, 'lib/footerHaptics.ts')));
});

test('motion tokens: new springs, hero/epic, ambient table, emphasized ease', () => {
  assert.deepEqual(SPRING.pop, { damping: 12, stiffness: 260, mass: 0.7 });
  assert.deepEqual(SPRING.rubber, { damping: 30, stiffness: 400, mass: 1 });
  assert.deepEqual(SPRING.fling, { damping: 22, stiffness: 140, mass: 1 });
  assert.equal(HERO_MS.hero, 600);
  assert.equal(HERO_MS.epic, 1400);
  assert.equal(AMBIENT_MS.shimmer, 1600);
  assert.deepEqual([...EASE.emphasized], [0.2, 0, 0, 1]);
});

test('the shimmer clock is shared and the skeleton reads it; no per-block repeat', () => {
  assert.match(read('lib/shimmerClock.ts'), /makeMutable/);
  const sk = read('components/Skeleton.tsx');
  assert.match(sk, /useShimmerClock/);
  assert.doesNotMatch(sk, /withRepeat/);
});

test('the Settings screen exposes both toggles', () => {
  const more = read('screens/MoreScreen.tsx');
  assert.match(more, /label="Haptics"/);
  assert.match(more, /label="Reduced effects"/);
});

test('TickNumber has a roll variant that does not run on the JS thread', () => {
  const t = read('components/TickNumber.tsx');
  assert.match(t, /variant\??:/);
  assert.match(t, /useAnimatedStyle/);
});

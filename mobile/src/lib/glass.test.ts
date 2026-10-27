import assert from 'node:assert/strict';
import { test } from 'node:test';

import { compositeOver, contrastRatio, darkGlass, lightGlass, parseRgba } from './glass.ts';

for (const [name, tokens] of [
  ['dark', darkGlass],
  ['light', lightGlass],
] as const) {
  test(`${name} glass is translucent, not opaque or invisible`, () => {
    const { a } = parseRgba(tokens.glass);
    assert.ok(a >= 0.4 && a <= 0.85, `glass alpha ${a} should let the background show through`);
    const border = parseRgba(tokens.glassBorder).a;
    assert.ok(border > 0 && border < 0.5);
    const inset = parseRgba(tokens.glassInset).a;
    assert.ok(inset > 0 && inset < 0.2);
  });
}

test('secondary text stays AA-readable on glass over its normal backgrounds', () => {
  for (const bg of ['#000000', '#0B1220', '#1A1F26']) {
    const fill = compositeOver(darkGlass.glass, bg);
    assert.ok(contrastRatio([0xa6, 0xb0, 0xbb], fill) >= 4.5, `dark on ${bg}`);
  }
  for (const bg of ['#EAF3F8', '#D9E8F0']) {
    const fill = compositeOver(lightGlass.glass, bg);
    assert.ok(contrastRatio([0x3e, 0x58, 0x67], fill) >= 4.5, `light on ${bg}`);
  }
});

test('glass input fill and rim are translucent and distinct from the card rim', () => {
  for (const tokens of [darkGlass, lightGlass]) {
    const fill = parseRgba(tokens.glassInput).a;
    assert.ok(fill > 0 && fill <= 0.7);
    assert.ok(parseRgba(tokens.glassInputBorder).a > 0);
  }
});

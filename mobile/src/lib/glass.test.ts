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

test('secondary and muted text stay AA-readable on glass over their normal backgrounds (web-synced ramp)', () => {
  for (const bg of ['#000000', '#0B1220', '#1f2226']) {
    const fill = compositeOver(darkGlass.glass, bg);
    assert.ok(contrastRatio([0xe5, 0xe7, 0xeb], fill) >= 4.5, `dark secondary on ${bg}`);
    assert.ok(contrastRatio([0xa8, 0xad, 0xb7], fill) >= 4.5, `dark muted on ${bg}`);
  }
  for (const bg of ['#eef3f6', '#e6edf1']) {
    const fill = compositeOver(lightGlass.glass, bg);
    assert.ok(contrastRatio([0x3b, 0x4a, 0x56], fill) >= 4.5, `light secondary on ${bg}`);
    assert.ok(contrastRatio([0x57, 0x64, 0x6f], fill) >= 4.5, `light muted on ${bg}`);
  }
});

test('glass input fill and rim are translucent and distinct from the card rim', () => {
  for (const tokens of [darkGlass, lightGlass]) {
    const fill = parseRgba(tokens.glassInput).a;
    assert.ok(fill > 0 && fill <= 0.7);
    assert.ok(parseRgba(tokens.glassInputBorder).a > 0);
  }
});

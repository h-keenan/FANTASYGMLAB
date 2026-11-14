import assert from 'node:assert/strict';
import test from 'node:test';

import { glowLayers, GLOW_LAYER_COUNT } from './avatarGlow.ts';

test('glow halo is a stack of faint discs, never one solid hard-edged disc', () => {
  const layers = glowLayers(8, 0.5);
  assert.equal(layers.length, GLOW_LAYER_COUNT);
  // Widest disc is the faintest: no single layer can read as an edge.
  assert.ok(layers.every((l) => l.opacity <= 0.12));
  // Spreads strictly increase, ending at the full spread.
  for (let i = 1; i < layers.length; i += 1) assert.ok(layers[i].spread > layers[i - 1].spread);
  assert.equal(layers[layers.length - 1].spread, 8);
  // Stacked alpha at the ring is bounded by the peak the tier asked for (plus a small bloom).
  const alphaAtRing = 1 - layers.reduce((a, l) => a * (1 - l.opacity), 1);
  assert.ok(alphaAtRing < 0.6);
});

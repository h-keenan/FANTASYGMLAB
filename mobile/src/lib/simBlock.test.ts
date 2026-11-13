// Run with: node --experimental-strip-types --test src/lib/simBlock.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simBlockTag, simStatusOptions } from './simGame.ts';

test('trade block chip: short labels for yours and the AI, nothing when not blocked', () => {
  assert.deepEqual(simBlockTag({ block: { by: '3', mine: true, looking_for: null, why: 'On your block' } }), { key: 'block', label: 'Your block', tone: 'accent' });
  assert.equal(simBlockTag({ block: { by: '7', mine: false, looking_for: 'RB', why: 'Selling depth' } })?.label, 'On block');
  assert.equal(simBlockTag({}), null);
});

test('the On the block filter only exists in a game with a trade block', () => {
  assert.equal(simStatusOptions(false).some((o) => o.value === 'block'), false);
  assert.deepEqual(simStatusOptions(true).at(-1), { value: 'block', label: 'On the block' });
});

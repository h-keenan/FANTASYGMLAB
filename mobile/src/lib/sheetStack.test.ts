// Run with: node --experimental-strip-types --test src/lib/sheetStack.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { createSheetStack } from './sheetStack.ts';

test('shows only the newest sheet and restores the previous one on close', () => {
  const stack = createSheetStack();
  stack.open('a');
  stack.open('b');
  assert.equal(stack.top(), 'b');
  assert.equal(stack.isHidden('a'), true);
  stack.close('b');
  assert.equal(stack.top(), 'a');
  assert.equal(stack.isHidden('a'), false);
});

test('ignores duplicate opens and unknown closes', () => {
  const stack = createSheetStack();
  let calls = 0;
  stack.subscribe(() => {
    calls += 1;
  });
  stack.open('a');
  stack.open('a');
  stack.close('zzz');
  assert.equal(calls, 1);
  assert.equal(stack.size(), 1);
});

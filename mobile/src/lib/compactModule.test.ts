import test from 'node:test';
import assert from 'node:assert/strict';
import { compactAriaLabel, compactParts, compactSummaryText, noticeDismissMs } from './compactModule.ts';

test('a collapsed summary drops empty parts, caps the line and reads as one status', () => {
  const parts = compactParts([{ key: 'a', text: 'R1 P2' }, null, false, '', { key: 'c', text: 'need RB/WR' }]);
  assert.equal(compactSummaryText(parts), 'R1 P2 · need RB/WR');
  assert.equal(compactParts(Array.from({ length: 9 }, (_, i) => ({ key: `k${i}`, text: `t${i}` }))).length, 6);
  assert.equal(compactAriaLabel('Draft clock', parts, false), 'Draft clock: R1 P2 · need RB/WR. Expand');
});

test('the shared notice toast: confirmations auto-dismiss, errors never', () => {
  assert.equal(noticeDismissMs('success'), 4000);
  assert.ok((noticeDismissMs('warning') ?? 0) > 4000);
  assert.equal(noticeDismissMs('danger'), null);
});

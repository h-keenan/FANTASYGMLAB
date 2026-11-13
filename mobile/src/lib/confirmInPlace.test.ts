// Run with: node --experimental-strip-types --test src/lib/confirmInPlace.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { TAP_AGAIN_REVERT_MS, confirmAnnouncement, reduceConfirm, revertMs } from './confirmInPlace.ts';

test('arms, confirms and finishes; a stray confirm while idle does nothing', () => {
  assert.equal(reduceConfirm('idle', 'arm'), 'armed');
  assert.equal(reduceConfirm('armed', 'confirm'), 'busy');
  assert.equal(reduceConfirm('busy', 'succeeded'), 'idle');
  assert.equal(reduceConfirm('idle', 'confirm'), 'idle');
});

test('failure lands in error, which can retry or cancel; busy never cancels', () => {
  assert.equal(reduceConfirm('busy', 'failed'), 'error');
  assert.equal(reduceConfirm('error', 'confirm'), 'busy');
  assert.equal(reduceConfirm('error', 'cancel'), 'idle');
  assert.equal(reduceConfirm('busy', 'timeout'), 'busy');
  assert.equal(reduceConfirm('armed', 'timeout'), 'idle');
});

test('tap-again reverts after 4 s; announcements name the next step', () => {
  assert.equal(revertMs('tap-again'), TAP_AGAIN_REVERT_MS);
  assert.equal(TAP_AGAIN_REVERT_MS, 4000);
  assert.match(confirmAnnouncement('armed', 'tap-again', { label: 'Sign out' }), /Tap again to confirm/);
  assert.equal(confirmAnnouncement('idle', 'ask', { label: 'x' }), '');
});

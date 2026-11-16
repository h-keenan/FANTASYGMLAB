// Run with: node --experimental-strip-types --test src/lib/simGamePlan.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { runSimGameCall } from './simGameCall.ts';
import { simGameGate } from './simGame.ts';

function handlers() {
  const log = { gates: [] as string[], errors: [] as string[] };
  return {
    log,
    h: { onGate: (g: { kind: string }) => log.gates.push(g.kind), onError: (m: string) => log.errors.push(m), retryMs: 0 },
  };
}

test('plan_unverified is a retryable unavailable state, not the paywall', () => {
  assert.deepEqual(simGameGate({ reason: 'plan_unverified', is_premium: null, preview: null } as never), { kind: 'unavailable', cause: 'plan' });
});

test('an unverified plan retries once, then reports a retryable message and never a gate', async () => {
  const { log, h } = handlers();
  let calls = 0;
  const body = await runSimGameCall(async () => (++calls, { reason: 'plan_unverified', is_premium: null, preview: null }) as never, h);
  assert.equal(body, null);
  assert.equal(calls, 2);
  assert.deepEqual(log.gates, []);
  assert.match(log.errors[0], /verify your plan/);
});

test('a verified-Pro answer tells the screen to clear any stale paywall', async () => {
  let cleared = 0;
  const { h } = handlers();
  const withHook = { ...h, onVerifiedPro: () => (cleared += 1) };
  await runSimGameCall(async () => ({ reason: '', is_premium: true, preview: null }) as never, withHook);
  await runSimGameCall(async () => ({ reason: '', is_premium: false, preview: { paywalled: false } }) as never, withHook);
  assert.equal(cleared, 1);
});

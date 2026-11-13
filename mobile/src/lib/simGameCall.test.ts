// Run with: node --experimental-strip-types --test src/lib/simGameCall.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { runSimGameCall } from './simGameCall.ts';

function handlers() {
  const log = { gates: [] as string[], errors: [] as string[] };
  return {
    log,
    h: { onGate: (g: { kind: string }) => log.gates.push(g.kind), onError: (m: string) => log.errors.push(m), retryMs: 0 },
  };
}

test('a storage failure on an action retries once and then succeeds without a gate', async () => {
  const { log, h } = handlers();
  let calls = 0;
  const body = await runSimGameCall(async () => (++calls === 1 ? { reason: 'sim_storage_unavailable', detail: 'http_5xx' } : { reason: '' }), h);
  assert.deepEqual(body, { reason: '' });
  assert.equal(calls, 2);
  assert.deepEqual(log, { gates: [], errors: [] });
});

test('a persistent storage failure is an inline error, never a full-screen gate', async () => {
  const { log, h } = handlers();
  const body = await runSimGameCall(async () => ({ reason: 'sim_storage_unavailable', detail: 'constraint' }), h);
  assert.equal(body, null);
  assert.deepEqual(log.gates, []);
  assert.match(log.errors[0], /Couldn't save that.*\(constraint\)/);
});

test('flag-off and conflicts keep their gates', async () => {
  const off = handlers();
  await runSimGameCall(async () => { throw { status: 404 }; }, off.h);
  assert.deepEqual(off.log.gates, ['unavailable']);
  const conflict = handlers();
  await runSimGameCall(async () => ({ reason: 'conflict' }), conflict.h);
  assert.deepEqual(conflict.log.gates, ['conflict']);
});

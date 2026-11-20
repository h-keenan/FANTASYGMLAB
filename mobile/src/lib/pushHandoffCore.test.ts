import test from 'node:test';
import assert from 'node:assert/strict';
import { settleWithin, unregisterThenDropSession } from './pushHandoffCore.ts';

test('unregister runs and finishes before the session is dropped', async () => {
  const order: string[] = [];
  await unregisterThenDropSession({
    unregisterPush: async () => {
      order.push('unregister:start');
      await new Promise((r) => setTimeout(r, 10));
      order.push('unregister:end');
    },
    dropSession: async () => {
      order.push('drop');
    },
  });
  assert.deepEqual(order, ['unregister:start', 'unregister:end', 'drop']);
});

test('a hanging unregister never blocks sign-out past the timeout', async () => {
  let dropped = false;
  const started = Date.now();
  await unregisterThenDropSession(
    {
      unregisterPush: () => new Promise<void>(() => {}),
      dropSession: async () => {
        dropped = true;
      },
    },
    { timeoutMs: 30 },
  );
  assert.equal(dropped, true);
  assert.ok(Date.now() - started < 1000);
});

test('a failing unregister still drops the session', async () => {
  let dropped = false;
  await unregisterThenDropSession({
    unregisterPush: async () => {
      throw new Error('offline');
    },
    dropSession: async () => {
      dropped = true;
    },
  });
  assert.equal(dropped, true);
});

test('kill switch off awaits unregister without a timeout, then drops', async () => {
  const order: string[] = [];
  await unregisterThenDropSession(
    {
      unregisterPush: async () => {
        await new Promise((r) => setTimeout(r, 40));
        order.push('unregister');
      },
      dropSession: async () => {
        order.push('drop');
      },
    },
    { enabled: false, timeoutMs: 1 },
  );
  assert.deepEqual(order, ['unregister', 'drop']);
});

test('settleWithin resolves on timeout', async () => {
  await settleWithin(() => new Promise(() => {}), 10);
});

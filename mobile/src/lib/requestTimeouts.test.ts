import assert from 'node:assert/strict';
import { test } from 'node:test';

import { BILLING_STATUS_UNKNOWN_MESSAGE, SLOW_REQUEST_MESSAGE } from './badDayCopy.ts';
import { CLIENT_TIMEOUT_CODE, isPostgrestRead, withReadTimeout } from './requestTimeouts.ts';

const REST = 'https://x.supabase.co/rest/v1/saved_leagues?select=*';
const hang: typeof fetch = (_input, init) =>
  new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  });

test('a hung PostgREST read becomes a 408 with the slow copy', async () => {
  const res = await withReadTimeout(hang, { message: SLOW_REQUEST_MESSAGE, timeoutMs: 20 })(REST);
  assert.equal(res.status, 408);
  assert.deepEqual(await res.json(), { message: SLOW_REQUEST_MESSAGE, code: CLIENT_TIMEOUT_CODE });
});

test('a fast read passes through', async () => {
  const ok: typeof fetch = async () => new Response('[]', { status: 200 });
  const res = await withReadTimeout(ok, { message: 'm', timeoutMs: 20 })(REST);
  assert.equal(res.status, 200);
});

test('writes and non-PostgREST calls are never timed out', async () => {
  let seen: AbortSignal | null | undefined = null;
  const spy: typeof fetch = async (_i, init) => {
    seen = init?.signal;
    return new Response('{}');
  };
  const f = withReadTimeout(spy, { message: 'm', timeoutMs: 20 });
  await f(REST, { method: 'PATCH' });
  assert.equal(seen, undefined);
  seen = null;
  await f('https://x.supabase.co/auth/v1/token');
  assert.equal(seen, undefined);
  assert.equal(isPostgrestRead(REST, { method: 'POST' }), false);
  assert.equal(isPostgrestRead(REST, { method: 'HEAD' }), true);
});

test('a caller abort is an error, not a timeout response', async () => {
  const caller = new AbortController();
  const p = withReadTimeout(hang, { message: 'm', timeoutMs: 1000 })(REST, { signal: caller.signal });
  caller.abort();
  await assert.rejects(p);
});

test('kill switch off is inert', async () => {
  let seen: AbortSignal | null | undefined = null;
  const spy: typeof fetch = async (_i, init) => {
    seen = init?.signal;
    return new Response('[]');
  };
  await withReadTimeout(spy, { message: 'm', timeoutMs: 20, enabled: false })(REST);
  assert.equal(seen, undefined);
});

test('billing write copy states the outcome is unknown', () => {
  assert.match(BILLING_STATUS_UNKNOWN_MESSAGE, /cannot say whether/);
  assert.doesNotMatch(BILLING_STATUS_UNKNOWN_MESSAGE, /failed|did not go through|succeeded/i);
});

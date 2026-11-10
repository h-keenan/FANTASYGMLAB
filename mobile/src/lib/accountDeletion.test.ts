import test from 'node:test';
import assert from 'node:assert/strict';
import { hasAppleIdentity, requestAccountDeletion } from './accountDeletion.ts';

const base = { supabaseUrl: 'https://p.supabase.test/', anonKey: 'anon', accessToken: 'jwt' };
const resp = (status: number, body: unknown) => ({ ok: status < 400, status, json: async () => body });

test('posts to delete-account with bearer and apple code when provided', async () => {
  let seen: { url: string; init: { headers: Record<string, string>; body: string } } | null = null;
  const out = await requestAccountDeletion({
    ...base,
    fetchFn: async (url, init) => { seen = { url, init }; return resp(200, { ok: true }); },
    getAppleAuthorizationCode: async () => 'code1',
  });
  assert.equal(out.error, null);
  assert.equal(seen!.url, 'https://p.supabase.test/functions/v1/delete-account');
  assert.equal(seen!.init.headers.Authorization, 'Bearer jwt');
  assert.deepEqual(JSON.parse(seen!.init.body), { apple_authorization_code: 'code1' });
});

test('apple re-auth failure does not block deletion', async () => {
  const out = await requestAccountDeletion({
    ...base,
    fetchFn: async (_u, init) => { assert.equal(init.body, '{}'); return resp(200, {}); },
    getAppleAuthorizationCode: async () => { throw new Error('cancelled'); },
  });
  assert.equal(out.error, null);
});

test('server refusal (billing cancel failed) surfaces its message', async () => {
  const out = await requestAccountDeletion({
    ...base,
    fetchFn: async () => resp(502, { ok: false, error: 'Could not cancel billing' }),
  });
  assert.equal(out.error, 'Could not cancel billing');
});

test('network failure returns an error, never throws', async () => {
  const out = await requestAccountDeletion({ ...base, fetchFn: async () => { throw new Error('offline'); } });
  assert.match(out.error!, /Could not reach/);
});

test('hasAppleIdentity', () => {
  assert.equal(hasAppleIdentity({ identities: [{ provider: 'apple' }] }), true);
  assert.equal(hasAppleIdentity({ identities: [{ provider: 'email' }] }), false);
  assert.equal(hasAppleIdentity(null), false);
});

// Run with: node --experimental-strip-types --test src/lib/accountEvents.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { detectAccountEvent, signupMethodOf } from './accountEvents.ts';

function store() {
  const m = new Map<string, string>();
  return {
    getItem: async (k: string) => m.get(k) ?? null,
    setItem: async (k: string, v: string) => {
      m.set(k, v);
    },
  };
}
const NOW = Date.parse('2026-11-26T12:00:00Z');
const iso = (minAgo: number) => new Date(NOW - minAgo * 60_000).toISOString();

test('signupMethodOf reads identities then app_metadata', () => {
  assert.equal(signupMethodOf({ identities: [{ provider: 'google' }] }), 'google');
  assert.equal(signupMethodOf({ app_metadata: { provider: 'apple' } }), 'apple');
  assert.equal(signupMethodOf({ app_metadata: { provider: 'github' } }), 'other');
});

test('new Apple/Google/email accounts are reported once', async () => {
  const s = store();
  for (const provider of ['google', 'apple', 'email']) {
    const user = { id: `u-${provider}`, created_at: iso(1), app_metadata: { provider } };
    assert.deepEqual(await detectAccountEvent(user, s, NOW), { event: 'signup_completed', method: provider });
    assert.equal(await detectAccountEvent(user, s, NOW), null);
  }
});

test('an old account signing in again is not a signup', async () => {
  const user = { id: 'u1', created_at: iso(60 * 24 * 40), app_metadata: { provider: 'apple' } };
  assert.equal(await detectAccountEvent(user, store(), NOW), null);
});

test('guest then upgrade: guest_session_started once, then signup_completed once', async () => {
  const s = store();
  const guest = { id: 'g1', is_anonymous: true, created_at: iso(1) };
  assert.deepEqual(await detectAccountEvent(guest, s, NOW), { event: 'guest_session_started' });
  assert.equal(await detectAccountEvent(guest, s, NOW), null);
  const upgraded = { id: 'g1', created_at: iso(200), identities: [{ provider: 'apple' }] };
  assert.deepEqual(await detectAccountEvent(upgraded, s, NOW), { event: 'signup_completed', method: 'apple' });
  assert.equal(await detectAccountEvent(upgraded, s, NOW), null);
});

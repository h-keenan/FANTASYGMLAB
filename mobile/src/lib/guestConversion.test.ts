// Run with: node --experimental-strip-types --test src/lib/guestConversion.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { canConvertGuestToAccount, validateGuestConversionInput } from './guestConversion.ts';

test('canConvertGuestToAccount: true only for a currently-anonymous session', () => {
  assert.equal(canConvertGuestToAccount({ user: { is_anonymous: true } }), true);
  assert.equal(canConvertGuestToAccount({ user: { is_anonymous: false } }), false);
  assert.equal(canConvertGuestToAccount({ user: {} }), false);
  assert.equal(canConvertGuestToAccount({}), false);
  assert.equal(canConvertGuestToAccount(null), false);
  assert.equal(canConvertGuestToAccount(undefined), false);
});

test('validateGuestConversionInput: rejects empty/malformed email', () => {
  assert.equal(validateGuestConversionInput('', 'password1'), 'Enter a valid email address.');
  assert.equal(validateGuestConversionInput('   ', 'password1'), 'Enter a valid email address.');
  assert.equal(validateGuestConversionInput('not-an-email', 'password1'), 'Enter a valid email address.');
});

test('validateGuestConversionInput: rejects short/empty password', () => {
  assert.equal(validateGuestConversionInput('a@b.com', ''), 'Password must be at least 6 characters.');
  assert.equal(validateGuestConversionInput('a@b.com', '123'), 'Password must be at least 6 characters.');
});

test('validateGuestConversionInput: null for acceptable input', () => {
  assert.equal(validateGuestConversionInput('a@b.com', 'password1'), null);
  assert.equal(validateGuestConversionInput('  a@b.com  ', 'password1'), null);
});

test('guestMustCreateAccountToBuy: guests blocked, signed-in and signed-out not flagged', async () => {
  const { guestMustCreateAccountToBuy } = await import('./guestConversion.ts');
  assert.equal(guestMustCreateAccountToBuy({ user: { is_anonymous: true } }), true);
  assert.equal(guestMustCreateAccountToBuy({ user: { is_anonymous: false } }), false);
  assert.equal(guestMustCreateAccountToBuy(null), false);
});

import {
  classifyGuestLinkError,
  exchangeIdToken,
  GUEST_EMAIL_EXISTS_MESSAGE,
  GUEST_IDENTITY_EXISTS_MESSAGE,
} from './guestConversion.ts';

test('classifyGuestLinkError maps Supabase errors', () => {
  assert.equal(classifyGuestLinkError({ code: 'identity_already_exists' }), 'identity-exists');
  assert.equal(classifyGuestLinkError({ message: 'Identity is already linked to another user' }), 'identity-exists');
  assert.equal(classifyGuestLinkError({ code: 'email_exists' }), 'email-exists');
  assert.equal(classifyGuestLinkError({ message: 'A user with this email address has already been registered' }), 'email-exists');
  assert.equal(classifyGuestLinkError({ code: 'manual_linking_disabled' }), 'link-unavailable');
  assert.equal(classifyGuestLinkError({ message: 'boom' }), 'other');
  assert.equal(classifyGuestLinkError(null), 'other');
});

function fakeClient(err: { code?: string; message?: string } | null = null) {
  const calls: string[] = [];
  return {
    calls,
    client: {
      signInWithIdToken: async () => {
        calls.push('signIn');
        return { error: err };
      },
      linkIdentity: async () => {
        calls.push('link');
        return { error: err };
      },
    },
  };
}

test('exchangeIdToken links (never signs in) for a guest', async () => {
  const f = fakeClient();
  const r = await exchangeIdToken(f.client, { provider: 'apple', token: 't', nonce: 'n', linkGuest: true });
  assert.deepEqual(f.calls, ['link']);
  assert.equal(r.error, null);
});

test('exchangeIdToken signs in normally when not a guest', async () => {
  const f = fakeClient();
  await exchangeIdToken(f.client, { provider: 'google', token: 't', linkGuest: false });
  assert.deepEqual(f.calls, ['signIn']);
});

test('exchangeIdToken: identity already exists gives plain message, no fallback sign-in', async () => {
  const f = fakeClient({ code: 'identity_already_exists', message: 'x' });
  const r = await exchangeIdToken(f.client, { provider: 'google', token: 't', linkGuest: true });
  assert.deepEqual(f.calls, ['link']);
  assert.equal(r.failure, 'identity-exists');
  assert.equal(r.error, GUEST_IDENTITY_EXISTS_MESSAGE);
});

test('exchangeIdToken: email exists message', async () => {
  const f = fakeClient({ code: 'email_exists', message: 'x' });
  const r = await exchangeIdToken(f.client, { provider: 'apple', token: 't', linkGuest: true });
  assert.equal(r.error, GUEST_EMAIL_EXISTS_MESSAGE);
});

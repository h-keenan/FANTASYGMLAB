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

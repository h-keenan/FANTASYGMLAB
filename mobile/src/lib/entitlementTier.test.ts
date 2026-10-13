// Run with: node --experimental-strip-types --test src/lib/entitlementTier.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  FREE,
  FRONT_OFFICE,
  PRO,
  isAtLeast,
  resolveEntitlementTier,
  type EntitlementActiveSource,
} from './entitlementTier.ts';

function customerInfoWith(active: Record<string, unknown>): EntitlementActiveSource {
  return { entitlements: { active } };
}

test('resolveEntitlementTier: no active entitlements resolves Free', () => {
  assert.equal(resolveEntitlementTier(customerInfoWith({})), FREE);
});

test('resolveEntitlementTier: the existing "premium" entitlement resolves Pro (unchanged mapping)', () => {
  assert.equal(resolveEntitlementTier(customerInfoWith({ premium: { isActive: true } })), PRO);
});

test('resolveEntitlementTier: the "front_office" entitlement resolves Front Office', () => {
  assert.equal(resolveEntitlementTier(customerInfoWith({ front_office: { isActive: true } })), FRONT_OFFICE);
});

test('resolveEntitlementTier: both active resolves Front Office (checked first — it implies Pro)', () => {
  assert.equal(
    resolveEntitlementTier(
      customerInfoWith({ premium: { isActive: true }, front_office: { isActive: true } }),
    ),
    FRONT_OFFICE,
  );
});

test('resolveEntitlementTier: an unrelated/unknown active entitlement does not grant any paid tier', () => {
  assert.equal(resolveEntitlementTier(customerInfoWith({ some_other_entitlement: { isActive: true } })), FREE);
});

test('isAtLeast: ordering is FREE < PRO < FRONT_OFFICE', () => {
  assert.equal(isAtLeast(FREE, FREE), true);
  assert.equal(isAtLeast(FREE, PRO), false);
  assert.equal(isAtLeast(FREE, FRONT_OFFICE), false);

  assert.equal(isAtLeast(PRO, FREE), true);
  assert.equal(isAtLeast(PRO, PRO), true);
  assert.equal(isAtLeast(PRO, FRONT_OFFICE), false);

  assert.equal(isAtLeast(FRONT_OFFICE, FREE), true);
  assert.equal(isAtLeast(FRONT_OFFICE, PRO), true);
  assert.equal(isAtLeast(FRONT_OFFICE, FRONT_OFFICE), true);
});

test('isAtLeast: a Front Office subscriber must never fail a "has paid access" (>= Pro) gate', () => {
  // This is the exact regression this whole change exists to prevent: before
  // the tier model, a single hardcoded 'premium' entitlement id meant a
  // Front Office-only subscriber (no 'premium' entitlement active) would be
  // silently treated as Free anywhere a boolean premium check gated access.
  const frontOfficeTier = resolveEntitlementTier(customerInfoWith({ front_office: { isActive: true } }));
  assert.equal(isAtLeast(frontOfficeTier, PRO), true);
});

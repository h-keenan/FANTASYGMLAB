/**
 * Tier model shared by revenuecat.ts — split into its own file so the pure
 * tier-ranking/resolution logic has no runtime dependency on
 * `react-native`/`react-native-purchases` (both of which pull in real
 * `react-native` source at runtime, which can't be loaded by plain Node —
 * see bestAvailableCardVisual.ts's doc comment for the same constraint).
 * Keeping this file free of that import is what makes it unit-testable
 * under this project's `node --experimental-strip-types --test` convention
 * (mobile has no jest/component-render test runner configured) — see
 * entitlementTier.test.ts.
 *
 * Mirrors modules/premium.py on the web exactly: three tiers, ordered
 * FREE < PRO < FRONT_OFFICE. Any caller that used to treat a boolean/
 * `entitlements.active['premium']` check as "has paid access" must keep
 * meaning "Pro or higher" now that Front Office exists — a bare equality/
 * identifier check against only `premium` would silently treat a Front
 * Office subscriber as a non-payer the moment that tier has real
 * subscribers.
 */

export type EntitlementTier = 'free' | 'pro' | 'front_office';

export const FREE: EntitlementTier = 'free';
export const PRO: EntitlementTier = 'pro';
export const FRONT_OFFICE: EntitlementTier = 'front_office';

const TIER_RANK: Record<EntitlementTier, number> = {
  [FREE]: 0,
  [PRO]: 1,
  [FRONT_OFFICE]: 2,
};

/**
 * True when `tier` is at `minimumTier` or a tier above it — mirrors web's
 * `premium.is_at_least()`. This is the one place tier ordering is defined;
 * callers should never hand-roll `tier === 'pro' || tier === 'front_office'`
 * comparisons.
 */
export function isAtLeast(tier: EntitlementTier, minimumTier: EntitlementTier): boolean {
  return TIER_RANK[tier] >= TIER_RANK[minimumTier];
}

// RevenueCat entitlement identifiers (dashboard-configured lookup keys —
// distinct from the tier names above). `premium` is the original,
// already-working entitlement and keeps mapping to the Pro tier exactly as
// before; it is never renamed or stopped being checked. `front_office` is
// the newly added entitlement for the Front Office tier — the store-side
// subscription products for it don't exist yet (pending manual App
// Store/Play Store setup outside this codebase), so it will simply have no
// active subscribers until that lands, but the identifier itself is already
// configured in RevenueCat and safe to check now.
export const PRO_ENTITLEMENT_ID = 'premium';
export const FRONT_OFFICE_ENTITLEMENT_ID = 'front_office';

/** Structural duck-type of RevenueCat's `CustomerInfo` — only the shape
 * actually used here, so this file never needs to import the real SDK
 * type (which would be harmless itself, being type-only, but keeping this
 * file dependency-free of react-native-purchases entirely is simplest). */
export interface EntitlementActiveSource {
  entitlements: {
    active: Record<string, unknown>;
  };
}

/**
 * Resolve the current entitlement tier from a RevenueCat `CustomerInfo`'s
 * active entitlements (or anything with the same shape). Front Office
 * implies Pro-level access too, so it is checked first; `premium` (the
 * existing entitlement) falls back to Pro; neither active resolves Free.
 * Mirrors the web's entitlement resolution order (modules/premium.py's
 * `_normalize_tier`/`get_entitlement_debug`).
 */
export function resolveEntitlementTier(info: EntitlementActiveSource): EntitlementTier {
  const active = info.entitlements.active;
  if (active[FRONT_OFFICE_ENTITLEMENT_ID]) return FRONT_OFFICE;
  if (active[PRO_ENTITLEMENT_ID]) return PRO;
  return FREE;
}

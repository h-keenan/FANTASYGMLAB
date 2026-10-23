/**
 * Free-trial length for a store product, read from what RevenueCat actually
 * returns for it (never hardcoded), so the paywall only promises a trial the
 * store will really grant. Structurally typed against react-native-purchases'
 * `PurchasesStoreProduct` so this file stays free of react-native imports and
 * runs under the plain `node --test` convention (see entitlementTier.ts).
 *
 * - App Store: a free trial is an `introPrice` with price 0.
 * - Google Play: a free trial is the default subscription option's
 *   `freePhase` (Play's introPrice can be null even when a trial exists).
 */
export interface TrialSourceProduct {
  introPrice?: { price: number; periodUnit: string; periodNumberOfUnits: number } | null;
  defaultOption?: { freePhase?: { billingPeriod: { unit: string; value: number } } | null } | null;
}

export interface FreeTrial {
  /** e.g. "3-day" — ready for "Start 3-day free trial". */
  lengthLabel: string;
}

const UNIT_LABELS: Record<string, string> = {
  DAY: 'day',
  WEEK: 'week',
  MONTH: 'month',
  YEAR: 'year',
};

function label(unit: string, count: number): string | null {
  const word = UNIT_LABELS[unit];
  if (!word || !Number.isFinite(count) || count <= 0) return null;
  return `${count}-${word}`;
}

export function freeTrialFor(product: TrialSourceProduct | null | undefined): FreeTrial | null {
  if (!product) return null;
  const intro = product.introPrice;
  if (intro && intro.price === 0) {
    const l = label(intro.periodUnit, intro.periodNumberOfUnits);
    if (l) return { lengthLabel: l };
  }
  const free = product.defaultOption?.freePhase;
  if (free) {
    const l = label(free.billingPeriod.unit, free.billingPeriod.value);
    if (l) return { lengthLabel: l };
  }
  return null;
}

/** Mirrors RevenueCat's INTRO_ELIGIBILITY_STATUS without importing it (this file stays node-testable). */
export type IntroEligibility = 'eligible' | 'ineligible' | 'unknown';

/**
 * The trial to advertise to THIS user, or null. A store product can carry a free
 * intro offer the user already used, so product data alone is not enough:
 * - iOS: `introPrice` is present whether or not the Apple ID is still eligible,
 *   so require RevenueCat to report 'eligible' (unknown/ineligible show no trial).
 * - Android: Play already resolves `defaultOption` to the best offer this account
 *   is eligible for, and the SDK reports eligibility as unknown, so trust the
 *   free phase unless eligibility is explicitly 'ineligible'.
 */
export function freeTrialForUser(
  product: TrialSourceProduct | null | undefined,
  eligibility: IntroEligibility | undefined,
  platform: string,
): FreeTrial | null {
  const trial = freeTrialFor(product);
  if (!trial) return null;
  if (eligibility === 'ineligible') return null;
  if (platform === 'ios') return eligibility === 'eligible' ? trial : null;
  return trial;
}

/** "Start 3-day free trial" */
export function trialCtaLabel(trial: FreeTrial): string {
  return `Start ${trial.lengthLabel} free trial`;
}

/** "Then $19.99/yr. Cancel anytime." using the store's own price string. */
export function thenPriceLine(priceString: string, suffix: string): string {
  return `Then ${priceString}${suffix}. Cancel anytime.`;
}

/** "Trial ends Oct 25" for a still-future ISO date, else "". */
export function trialEndLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '';
  const end = new Date(iso);
  if (Number.isNaN(end.getTime()) || end.getTime() <= now.getTime()) return '';
  return `Trial ends ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
}

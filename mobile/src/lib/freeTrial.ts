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
  /** e.g. "7-day" — ready for "Start your 7-day free trial". */
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

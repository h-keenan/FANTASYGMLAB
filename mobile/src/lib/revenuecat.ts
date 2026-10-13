import { Platform } from 'react-native';
import Purchases, {
  PURCHASES_ERROR_CODE,
  type PurchasesError,
  type PurchasesOffering,
  type PurchasesPackage,
} from 'react-native-purchases';

import { env } from './env';
import {
  FREE,
  FRONT_OFFICE,
  PRO,
  PRO_ENTITLEMENT_ID,
  isAtLeast,
  resolveEntitlementTier,
  type EntitlementTier,
} from './entitlementTier';

export { FREE, FRONT_OFFICE, PRO, isAtLeast, resolveEntitlementTier, type EntitlementTier };

/** Back-compat alias for the pre-existing exported name. */
const PREMIUM_ENTITLEMENT_ID = PRO_ENTITLEMENT_ID;

let configured = false;

/** Call once at app startup, after we know whether an SDK key exists for this platform. */
export function configureRevenueCat(): void {
  if (configured) return;
  const apiKey = Platform.select({
    ios: env.revenueCatIosKey,
    android: env.revenueCatAndroidKey,
    default: '',
  });
  if (!apiKey) {
    // Web/dev fallback or a platform without a key yet — purchases simply
    // won't be available; entitlement still comes from Supabase profiles.
    return;
  }
  Purchases.configure({ apiKey });
  configured = true;
}

/** Attach the signed-in Supabase user id so RevenueCat and our backend agree on identity. */
export async function identifyRevenueCatUser(supabaseUserId: string): Promise<void> {
  if (!configured) return;
  await Purchases.logIn(supabaseUserId);
}

export async function signOutRevenueCatUser(): Promise<void> {
  if (!configured) return;
  await Purchases.logOut();
}

/** The current entitlement tier ('free' | 'pro' | 'front_office'), resolved
 * from RevenueCat. Not configured (no SDK key for this platform) resolves
 * Free, matching every other "not configured" fallback in this module. */
export async function getEntitlementTier(): Promise<EntitlementTier> {
  if (!configured) return FREE;
  const info = await Purchases.getCustomerInfo();
  return resolveEntitlementTier(info);
}

/**
 * Back-compat: true for Pro **or** Front Office (i.e. "has paid access") —
 * same meaning this function had before Front Office existed, just widened
 * rather than rewritten, mirroring the web's PR #996 treatment of
 * `premium.is_premium_user()`. Existing call sites that gate on this as a
 * plain paying-customer check keep working unchanged and now correctly
 * include Front Office subscribers too.
 */
export async function hasPremiumEntitlement(): Promise<boolean> {
  return isAtLeast(await getEntitlementTier(), PRO);
}

/** True only for the Front Office tier specifically (not just "paid"). */
export async function hasFrontOfficeEntitlement(): Promise<boolean> {
  return (await getEntitlementTier()) === FRONT_OFFICE;
}

/** The current offering (dashboard-configured), or null if unavailable. */
export async function getCurrentOffering(): Promise<PurchasesOffering | null> {
  if (!configured) return null;
  const offerings = await Purchases.getOfferings();
  return offerings.current;
}

export interface PurchaseOutcome {
  /** True once the purchase completed and at least the Pro entitlement is
   * active (kept for backward compatibility with existing callers — see
   * `hasPremiumEntitlement` above for why this now also covers Front
   * Office). */
  purchased: boolean;
  /** True if the user backed out of the store sheet — not an error, don't show one. */
  cancelled: boolean;
  /** Set only for a genuine failure the user should be told about. */
  errorMessage?: string;
  /** The resolved tier after the purchase, when one completed. Front Office
   * has no purchasable store products yet, so this is 'pro' for every
   * purchase this app can currently offer — exposed for forward
   * compatibility once Front Office products exist. */
  tier?: EntitlementTier;
}

/** Buy a package and report a plain outcome — callers don't need to know RevenueCat's error shape. */
export async function purchasePackage(pack: PurchasesPackage): Promise<PurchaseOutcome> {
  if (!configured) {
    return { purchased: false, cancelled: false, errorMessage: 'Purchases are not available on this build.' };
  }
  try {
    const { customerInfo } = await Purchases.purchasePackage(pack);
    const tier = resolveEntitlementTier(customerInfo);
    return { purchased: isAtLeast(tier, PRO), cancelled: false, tier };
  } catch (e) {
    const error = e as PurchasesError;
    if (error.code === PURCHASES_ERROR_CODE.PURCHASE_CANCELLED_ERROR) {
      return { purchased: false, cancelled: true };
    }
    return { purchased: false, cancelled: false, errorMessage: error.message ?? 'Purchase failed.' };
  }
}

/** Re-sync entitlement state without a purchase — used after "Restore purchases". */
export async function restorePurchases(): Promise<boolean> {
  if (!configured) return false;
  const info = await Purchases.restorePurchases();
  return isAtLeast(resolveEntitlementTier(info), PRO);
}

export { PREMIUM_ENTITLEMENT_ID };

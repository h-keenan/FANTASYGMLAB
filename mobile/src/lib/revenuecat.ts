import { Platform } from 'react-native';
import Purchases, {
  PURCHASES_ERROR_CODE,
  type PurchasesError,
  type PurchasesOffering,
  type PurchasesPackage,
} from 'react-native-purchases';

import { env } from './env';

const PREMIUM_ENTITLEMENT_ID = 'premium';

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

export async function hasPremiumEntitlement(): Promise<boolean> {
  if (!configured) return false;
  const info = await Purchases.getCustomerInfo();
  return Boolean(info.entitlements.active[PREMIUM_ENTITLEMENT_ID]);
}

/** The current offering (dashboard-configured — "Founder Beta" at the time of writing), or null if unavailable. */
export async function getCurrentOffering(): Promise<PurchasesOffering | null> {
  if (!configured) return null;
  const offerings = await Purchases.getOfferings();
  return offerings.current;
}

export interface PurchaseOutcome {
  /** True once the purchase completed and the premium entitlement is active. */
  purchased: boolean;
  /** True if the user backed out of the store sheet — not an error, don't show one. */
  cancelled: boolean;
  /** Set only for a genuine failure the user should be told about. */
  errorMessage?: string;
}

/** Buy a package and report a plain outcome — callers don't need to know RevenueCat's error shape. */
export async function purchasePackage(pack: PurchasesPackage): Promise<PurchaseOutcome> {
  if (!configured) {
    return { purchased: false, cancelled: false, errorMessage: 'Purchases are not available on this build.' };
  }
  try {
    const { customerInfo } = await Purchases.purchasePackage(pack);
    return { purchased: Boolean(customerInfo.entitlements.active[PREMIUM_ENTITLEMENT_ID]), cancelled: false };
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
  return Boolean(info.entitlements.active[PREMIUM_ENTITLEMENT_ID]);
}

export { PREMIUM_ENTITLEMENT_ID };

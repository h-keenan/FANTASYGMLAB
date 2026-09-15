import { Platform } from 'react-native';
import Purchases from 'react-native-purchases';

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

export { PREMIUM_ENTITLEMENT_ID };

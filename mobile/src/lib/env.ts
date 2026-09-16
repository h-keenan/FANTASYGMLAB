/**
 * Central place to read required EXPO_PUBLIC_ env vars with a clear failure
 * mode instead of a silent `undefined` reaching the Supabase/RevenueCat SDKs.
 */

function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing ${name}. Copy mobile/.env.example to mobile/.env and fill it in.`,
    );
  }
  return value;
}

export const env = {
  supabaseUrl: requireEnv(
    'EXPO_PUBLIC_SUPABASE_URL',
    process.env.EXPO_PUBLIC_SUPABASE_URL,
  ),
  supabaseAnonKey: requireEnv(
    'EXPO_PUBLIC_SUPABASE_ANON_KEY',
    process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,
  ),
  apiBaseUrl: requireEnv(
    'EXPO_PUBLIC_API_BASE_URL',
    process.env.EXPO_PUBLIC_API_BASE_URL,
  ),
  revenueCatIosKey: process.env.EXPO_PUBLIC_REVENUECAT_IOS_SDK_KEY ?? '',
  revenueCatAndroidKey: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_SDK_KEY ?? '',
  // Defaults are Google's published, permanent AdMob test unit IDs — they
  // always fill with a test creative, so rewarded-ad unlock works out of
  // the box before a real AdMob account/app is set up. Swap in production
  // IDs (and mobile/app.json's react-native-google-mobile-ads app IDs) once
  // that account exists — same pattern as the Apple/RevenueCat keys.
  admobIosRewardedUnitId:
    process.env.EXPO_PUBLIC_ADMOB_IOS_REWARDED_UNIT_ID ?? 'ca-app-pub-3940256099942544/1712485313',
  admobAndroidRewardedUnitId:
    process.env.EXPO_PUBLIC_ADMOB_ANDROID_REWARDED_UNIT_ID ?? 'ca-app-pub-3940256099942544/5224354917',
  // No default — Google sign-in stays hidden until a real OAuth client
  // exists (Google Cloud Console). iOS/Android need their own native
  // client IDs; Web is required too since it's what Supabase's Google
  // provider itself is configured with (used as the `aud` fallback here).
  googleIosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? '',
  googleAndroidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? '',
  googleWebClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '',
};

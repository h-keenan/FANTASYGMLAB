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
};

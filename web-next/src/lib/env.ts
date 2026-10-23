/**
 * Central place to read required NEXT_PUBLIC_ env vars with a clear failure
 * mode instead of a silent `undefined` reaching the Supabase SDK or fetch
 * calls. Mirrors mobile/src/lib/env.ts's requireEnv pattern.
 */

function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing ${name}. Copy web-next/.env.example to web-next/.env.local and fill it in.`);
  }
  return value;
}

export const env = {
  supabaseUrl: requireEnv("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
  // Local dev default matches mobile/.env.example's EXPO_PUBLIC_API_BASE_URL
  // convention: points at a locally running
  // `uvicorn services.mobile_api_service:app --port 8000`.
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
};

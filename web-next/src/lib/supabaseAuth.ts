import { AuthClient } from "@supabase/auth-js";

import { env } from "./env";
import { baseUrl, storageKey } from "./supabaseKeys";

/**
 * The real GoTrue auth client (~100 KB of JS). Nothing imports this file
 * statically: `lib/supabase.ts` loads it with `import()` so it stays out of the
 * shared first-load chunk, and answers `getSession()` from the stored session
 * until it arrives. Construction is exactly what `lib/supabase.ts` did before
 * the split (same storage key, same implicit flow, same URL-session detection),
 * so a signed-in user's stored session keeps working untouched.
 */
export const auth = new AuthClient({
  url: new URL("auth/v1", baseUrl).href,
  headers: { Authorization: `Bearer ${env.supabaseAnonKey}`, apikey: env.supabaseAnonKey },
  storageKey,
  autoRefreshToken: true,
  persistSession: true,
  detectSessionInUrl: true,
  flowType: "implicit",
});

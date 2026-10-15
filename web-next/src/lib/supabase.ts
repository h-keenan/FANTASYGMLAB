import { createClient } from "@supabase/supabase-js";

import { env } from "./env";

/**
 * Mirrors mobile/src/lib/supabase.ts exactly, swapping AsyncStorage for
 * localStorage (supabase-js's browser default) and enabling
 * `detectSessionInUrl` — unlike React Native, Next.js runs in a real
 * browser tab, so email-confirmation / password-recovery / OAuth redirect
 * links need the client to parse the session out of the URL on landing.
 */
export const supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

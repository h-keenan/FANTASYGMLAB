import { AuthClient } from "@supabase/auth-js";
import { PostgrestClient } from "@supabase/postgrest-js";

import { env } from "./env";

/**
 * Mirrors mobile/src/lib/supabase.ts exactly, swapping AsyncStorage for
 * localStorage (supabase-js's browser default) and enabling
 * `detectSessionInUrl` — unlike React Native, Next.js runs in a real
 * browser tab, so email-confirmation / password-recovery / OAuth redirect
 * links need the client to parse the session out of the URL on landing.
 *
 * Built from `@supabase/auth-js` + `@supabase/postgrest-js` directly instead
 * of `createClient()` from `@supabase/supabase-js`. This app only uses
 * `supabase.auth.*` and `supabase.from(...)`; the umbrella client also
 * constructs (and therefore bundles) the Realtime websocket, Storage and
 * Edge Functions clients, which nothing here calls. Dropping them takes
 * ~100 KB (28 KB gzip) off the first-load JS of every route, which is the
 * shared layout chunk (see docs/performance-audit-client-2026-11.md).
 *
 * The wiring below is the same one SupabaseClient's constructor does:
 *  - same `sb-<project-ref>-auth-token` storage key, so existing signed-in
 *    sessions in users' localStorage keep working untouched;
 *  - the auth client is given the anon key as `apikey`/`Authorization`;
 *  - table queries carry `apikey` plus the signed-in user's access token
 *    as the Bearer (falling back to the anon key when signed out), so row
 *    level security sees the same identity as before.
 */
const baseUrl = new URL(env.supabaseUrl);
const storageKey = `sb-${baseUrl.hostname.split(".")[0]}-auth-token`;

const auth = new AuthClient({
  url: new URL("auth/v1", baseUrl).href,
  headers: { Authorization: `Bearer ${env.supabaseAnonKey}`, apikey: env.supabaseAnonKey },
  storageKey,
  autoRefreshToken: true,
  persistSession: true,
  detectSessionInUrl: true,
  flowType: "implicit",
});

const fetchWithSession: typeof fetch = async (input, init) => {
  const { data } = await auth.getSession();
  const headers = new Headers(init?.headers);
  if (!headers.has("apikey")) headers.set("apikey", env.supabaseAnonKey);
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${data.session?.access_token ?? env.supabaseAnonKey}`);
  }
  return fetch(input, { ...init, headers });
};

const rest = new PostgrestClient(new URL("rest/v1", baseUrl).href, {
  schema: "public",
  fetch: fetchWithSession,
});

export const supabase = {
  auth,
  from: rest.from.bind(rest),
};

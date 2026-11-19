import { env } from "./env";

/** Shared by the lazy auth client and the stored-session fast path in `supabase.ts`. */
export const baseUrl = new URL(env.supabaseUrl);
/** Same `sb-<project-ref>-auth-token` key supabase-js uses, so existing sessions keep working. */
export const storageKey = `sb-${baseUrl.hostname.split(".")[0]}-auth-token`;

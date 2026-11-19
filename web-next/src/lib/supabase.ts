import type { AuthChangeEvent, AuthClient as AuthClientClass, Session, Subscription } from "@supabase/auth-js";
import { PostgrestClient } from "@supabase/postgrest-js";

import { SLOW_REQUEST_MESSAGE } from "./badDayCopy";
import { env } from "./env";
import { withReadTimeout } from "./requestTimeouts";
import { baseUrl, storageKey } from "./supabaseKeys";

/**
 * Mirrors mobile/src/lib/supabase.ts, swapping AsyncStorage for localStorage
 * and enabling `detectSessionInUrl` (email-confirmation / password-recovery /
 * OAuth redirect links land in a real browser tab).
 *
 * Built from `@supabase/auth-js` + `@supabase/postgrest-js` directly instead
 * of `createClient()`: this app only uses `supabase.auth.*` and
 * `supabase.from(...)`, so the Realtime/Storage/Functions clients are never
 * bundled (see docs/performance-audit-client-2026-11.md).
 *
 * The GoTrue client itself (~100 KB, the second-largest piece of the shared
 * first-load JS after React) is no longer in that chunk. `supabase.auth` is a
 * facade with the same method surface; `lib/supabaseAuth.ts` is loaded with
 * `import()`:
 *  - immediately, the first time something needs the real client (sign in/out,
 *    a link callback in the URL, no usable stored session, an expired one);
 *  - otherwise when the browser is idle after first paint, so auth state
 *    changes (refresh, other-tab sign-out) are still observed.
 * Until then `getSession()` answers from the session auth-js itself persisted
 * (`sb-<ref>-auth-token`), but only while its access token has comfortably
 * more than the refresh margin left; an expired or near-expiry token always
 * goes through the real client, which refreshes it. After the real client
 * exists every call goes to it. The first API request therefore no longer
 * waits for the auth chunk to download and initialise.
 */

type Auth = InstanceType<typeof AuthClientClass>;

type AuthMethod =
  | "signInAnonymously"
  | "signInWithOAuth"
  | "signInWithPassword"
  | "signOut"
  | "signUp"
  | "linkIdentity"
  | "resetPasswordForEmail"
  | "updateUser";

let authPromise: Promise<Auth> | null = null;
/** Idle-deferred listeners waiting to learn that someone else already started the load. */
const loadWaiters: Array<() => void> = [];

/** Load (once) and return the real auth client. */
export function loadAuth(): Promise<Auth> {
  if (!authPromise) {
    const promise = import("./supabaseAuth").then((m) => m.auth);
    authPromise = promise;
    // A failed chunk load must be retryable, not cached forever.
    promise.catch(() => {
      if (authPromise === promise) authPromise = null;
    });
    loadWaiters.splice(0).forEach((wake) => wake());
  }
  return authPromise;
}

/**
 * Load the real client when the browser is idle after first paint, or as soon as
 * anything else starts the load (so a sign-in's own auth event is never missed).
 */
function loadAuthWhenIdle(): Promise<Auth> {
  if (authPromise || typeof window === "undefined") return loadAuth();
  return new Promise((resolve, reject) => {
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      loadAuth().then(resolve, reject);
    };
    loadWaiters.push(go);
    const ric = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number })
      .requestIdleCallback;
    if (ric) ric.call(window, go, { timeout: 4000 });
    else window.setTimeout(go, 2000);
  });
}

/** Seconds of access-token life below which the stored session is not trusted (auth-js refreshes at ~10 s). */
const FAST_PATH_MIN_TTL_SECONDS = 120;
const AUTH_CALLBACK_PARAM = /[#&?](access_token|refresh_token|code|error|error_code|error_description|type)=/;

/** The session auth-js persisted, if it is safe to use without constructing the client. */
export function peekStoredSession(now: number = Date.now()): Session | null {
  if (typeof window === "undefined") return null;
  try {
    // A callback URL (OAuth / email-confirm / recovery) must be parsed by the real client first.
    if (AUTH_CALLBACK_PARAM.test(window.location.hash) || AUTH_CALLBACK_PARAM.test(window.location.search)) return null;
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const stored = JSON.parse(raw) as Partial<Session> | null;
    if (!stored || typeof stored.access_token !== "string" || !stored.access_token || !stored.refresh_token || !stored.user) {
      return null;
    }
    if (typeof stored.expires_at !== "number" || stored.expires_at - now / 1000 < FAST_PATH_MIN_TTL_SECONDS) return null;
    return stored as Session;
  } catch {
    return null;
  }
}

function lazyMethod<K extends AuthMethod>(name: K): Auth[K] {
  return (async (...args: unknown[]) => {
    const client = await loadAuth();
    return (client[name] as (...a: unknown[]) => unknown)(...args);
  }) as unknown as Auth[K];
}

const auth = {
  async getSession() {
    if (!authPromise) {
      const session = peekStoredSession();
      if (session) return { data: { session }, error: null } as Awaited<ReturnType<Auth["getSession"]>>;
    }
    return (await loadAuth()).getSession();
  },
  onAuthStateChange(callback: (event: AuthChangeEvent, session: Session | null) => void | Promise<void>) {
    let subscription: Subscription | null = null;
    let cancelled = false;
    void loadAuthWhenIdle().then((client) => {
      if (!cancelled) subscription = client.onAuthStateChange(callback).data.subscription;
    });
    const handle: Subscription = {
      id: "lazy",
      callback,
      unsubscribe() {
        cancelled = true;
        subscription?.unsubscribe();
      },
    };
    return { data: { subscription: handle } };
  },
  signInAnonymously: lazyMethod("signInAnonymously"),
  signInWithOAuth: lazyMethod("signInWithOAuth"),
  signInWithPassword: lazyMethod("signInWithPassword"),
  signOut: lazyMethod("signOut"),
  signUp: lazyMethod("signUp"),
  linkIdentity: lazyMethod("linkIdentity"),
  resetPasswordForEmail: lazyMethod("resetPasswordForEmail"),
  updateUser: lazyMethod("updateUser"),
};

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
  // The one place PostgREST reads get a client timeout (lib/requestTimeouts.ts); writes are never timed out.
  fetch: withReadTimeout(fetchWithSession, { message: SLOW_REQUEST_MESSAGE }),
});

export const supabase = {
  auth,
  from: rest.from.bind(rest),
};

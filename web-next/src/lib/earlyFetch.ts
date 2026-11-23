/**
 * Early first-paint fetch for the Today (dashboard) page.
 *
 * Today the first API call leaves only after the JS bundle has downloaded and hydrated (about 2.5 s in on fast 3G with a 4x
 * CPU slowdown). A tiny inline script in <head> (EARLY_FETCH_SCRIPT, rendered by app/layout.tsx) starts the one request that
 * gates Today's first paint as soon as the HTML arrives; lib/api.ts then consumes that in-flight request instead of sending its
 * own (takeEarlyFetch). Design: docs/design/cookie-session-auth.md, "Alternatives: early-fetch inline script".
 *
 * Safety contract (each point has a test in earlyFetch.test.ts):
 *  - The script reads the session auth-js already persisted (`sb-<ref>-auth-token`, the same key supabase.ts peeks). It writes
 *    nothing new anywhere and logs nothing. The access token only ever goes in an Authorization header to the configured API
 *    origin, exactly like lib/api.ts. It is never put in a URL and never stored on `window`: the global holds only the
 *    in-flight request (url, user id, league id, promise).
 *  - On "/" (a returning user opening the bare site, who is about to be redirected to their league) it fires for the league
 *    remembered in `fgl.lastLeague.v1` when that entry belongs to the same signed-in user, so the request is in flight while
 *    the bundle downloads and the redirect resolves. With no remembered league it does nothing.
 *  - It does not fire when there is no session, the stored token has < 120 s left (the same floor supabase.ts uses for its fast
 *    path, so an expiring token goes through the real client and its refresh), on any auth callback URL (OAuth / email-confirm /
 *    recovery, which the real client must parse first), or off the /dashboard/<league> route and "/".
 *  - The global is single-use and short-lived: cleared when consumed and after EARLY_FETCH_TTL_MS if nobody takes it.
 *  - The result is bound to the user id and league id it was fetched for, and to the exact URL (path + lens + query, so the
 *    request cache key is the same as today's). If the signed-in user, league or URL differs, the early response is ignored
 *    and the app fetches normally; a rejected early request also falls back to a normal fetch. Response handling, error
 *    mapping and the coalescing key are all unchanged because the consumer feeds the response into the same code path.
 *  - The script is inline like THEME_BOOT_SCRIPT and is allowed by a sha256 hash in the CSP (constant per build; src/proxy.ts, lib/csp.ts,
 *    components/BootScripts.tsx), never by a blanket 'unsafe-inline'.
 */

/** `window` property holding the in-flight early request. */
export const EARLY_FETCH_GLOBAL = "__fdEarly";
/** An unclaimed early request is dropped this long after it started. */
export const EARLY_FETCH_TTL_MS = 30_000;
/** Same floor as supabase.ts FAST_PATH_MIN_TTL_SECONDS: below this the real auth client must run (and refresh). */
export const EARLY_FETCH_MIN_TTL_SECONDS = 120;
/** Where valuation lens detection is remembered (ValuationLensContext.DETECTED_LENS_STORAGE_KEY). */
const LENS_STORAGE_KEY = "fgl.detectedLens.v1";
/** Where the last-opened league is remembered (lib/lastLeagueHint.ts). */
const LAST_LEAGUE_STORAGE_KEY = "fgl.lastLeague.v1";

export interface EarlyFetch {
  url: string;
  uid: string;
  lid: string;
  p: Promise<Response>;
}

/** Inline script source. `apiBase` is the API origin (env.apiBaseUrl), `storageKey` the auth-js storage key. */
export function buildEarlyFetchScript({ apiBase, storageKey }: { apiBase: string; storageKey: string }): string {
  // JSON.stringify gives valid JS string literals; escape "<" so a value can never close the script element.
  const lit = (value: string) => JSON.stringify(value).replace(/</g, "\\u003c");
  return (
    "(function(){try{" +
    'var m=/^\\/dashboard\\/([^\\/]+)\\/?$/.exec(location.pathname);var home=location.pathname==="/";if(!m&&!home)return;' +
    "var cb=/[#&?](access_token|refresh_token|code|error|error_code|error_description|type)=/;" +
    "if(cb.test(location.hash)||cb.test(location.search))return;" +
    "var raw=localStorage.getItem(" + lit(storageKey) + ");if(!raw)return;" +
    "var s=JSON.parse(raw);" +
    'if(!s||typeof s.access_token!=="string"||!s.access_token||!s.refresh_token||!s.user||typeof s.user.id!=="string"||!s.user.id)return;' +
    'if(typeof s.expires_at!=="number"||s.expires_at-Date.now()/1000<' + EARLY_FETCH_MIN_TTL_SECONDS + ")return;" +
    "var lid;if(m){lid=decodeURIComponent(m[1])}else{" +
    "var L=JSON.parse(localStorage.getItem(" + lit(LAST_LEAGUE_STORAGE_KEY) + ")||\"null\");" +
    'if(!L||L.uid!==s.user.id||typeof L.id!=="string"||!L.id)return;lid=L.id}' +
    "var lens=\"Dynasty\";" +
    "try{var d=JSON.parse(localStorage.getItem(" + lit(LENS_STORAGE_KEY) + ")||\"null\");if(d&&d[lid]===\"Non-Dynasty\")lens=\"Non-Dynasty\"}catch(e){}" +
    'var url=' + lit(apiBase) + '+"/v1/leagues/"+encodeURIComponent(lid)+"/dashboard?lens="+encodeURIComponent(lens)+"&defer_trade_ideas=true";' +
    'var p=fetch(url,{headers:{Authorization:"Bearer "+s.access_token}});p.catch(function(){});' +
    "var e={url:url,uid:s.user.id,lid:lid,p:p};window." + EARLY_FETCH_GLOBAL + "=e;" +
    "setTimeout(function(){if(window." + EARLY_FETCH_GLOBAL + "===e)window." + EARLY_FETCH_GLOBAL + "=undefined}," + EARLY_FETCH_TTL_MS + ");" +
    "}catch(e){}})();"
  );
}

function leagueIdOf(url: string): string | null {
  const match = /\/v1\/leagues\/([^/?]+)\/dashboard\?/.exec(url);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

/**
 * Claim the early request for exactly this URL and signed-in user, or null. Leaves it in place when the URL is merely a
 * different request (other calls happen first); drops it when the URL matches but the user or league does not.
 */
export function takeEarlyFetch(url: string, userId: string | undefined): Promise<Response> | null {
  if (typeof window === "undefined") return null;
  const holder = window as unknown as Record<string, EarlyFetch | undefined>;
  const early = holder[EARLY_FETCH_GLOBAL];
  if (!early || early.url !== url) return null;
  holder[EARLY_FETCH_GLOBAL] = undefined;
  if (!userId || early.uid !== userId || early.lid !== leagueIdOf(url)) {
    early.p.catch(() => {});
    return null;
  }
  return early.p;
}

/**
 * The response for a request: the claimed early one when it settles in time and succeeds, otherwise `doFetch()` (a rejected or
 * aborted early request refetches, so a failure here is never worse than today's).
 */
export async function earlyOrFetch(
  early: Promise<Response> | null,
  signal: AbortSignal,
  doFetch: () => Promise<Response>,
): Promise<Response> {
  if (!early) return doFetch();
  try {
    return await new Promise<Response>((resolve, reject) => {
      if (signal.aborted) return reject(new Error("aborted"));
      const onAbort = () => reject(new Error("aborted"));
      signal.addEventListener("abort", onAbort, { once: true });
      early.then(
        (response) => {
          signal.removeEventListener("abort", onAbort);
          resolve(response);
        },
        (error) => {
          signal.removeEventListener("abort", onAbort);
          reject(error);
        },
      );
    });
  } catch {
    return doFetch();
  }
}

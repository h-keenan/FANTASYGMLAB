import { env } from "./env";
import { supabase } from "./supabase";

/**
 * Client for services/mobile_api_service.py's `POST /v1/analytics/event` —
 * the fix for a real bug: web-next (and mobile) never called into
 * modules/launch_analytics.py at all, so the `analytics_events` table
 * stayed empty despite real user traffic. That module's track_* functions
 * expect a Streamlit-session-state-shaped `state` dict to mint-once-and-
 * persist a stable per-browser anonymous id across reruns
 * (modules.launch_analytics.anonymous_id) — a stateless Next.js client has
 * no equivalent of Streamlit's `st.session_state`, so THIS module is that
 * equivalent: it mints the id once and persists it in localStorage instead.
 *
 * Deliberately minimal for this pass — only `trackPageView` and
 * `trackFeatureUse` (see docs/founder-beta-product-analytics-contract.md /
 * modules/launch_analytics.py's TRACKED_EVENTS for the full taxonomy; most
 * of it is a later follow-up, not this pass).
 */

const ANON_ID_STORAGE_KEY = "dynastygm_analytics_anon_id";

function randomHex16(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 16);
  }
  // crypto.randomUUID is unavailable only in non-browser/non-secure-context
  // test environments — good enough for a client-side dedupe/attribution
  // id that is never a security boundary.
  let out = "";
  for (let i = 0; i < 16; i += 1) {
    out += Math.floor(Math.random() * 16).toString(16);
  }
  return out;
}

let cachedAnonId: string | null = null;

/**
 * Stable per-browser anonymous id — same `anon_<hex16>` shape
 * modules.launch_analytics.anonymous_id() mints server-side, so a row looks
 * identical regardless of which client produced it. Exported for tests;
 * real callers should go through trackPageView/trackFeatureUse instead.
 *
 * Every localStorage access is wrapped in try/catch — it can throw in
 * private browsing / blocked-storage contexts, and analytics must never be
 * able to break the page it's instrumenting. A thrown read/write just means
 * a fresh id gets minted (and re-attempted to persist) on the next call.
 */
export function getOrCreateAnonId(): string {
  if (cachedAnonId) return cachedAnonId;
  try {
    const existing = window.localStorage.getItem(ANON_ID_STORAGE_KEY);
    if (existing) {
      cachedAnonId = existing;
      return existing;
    }
  } catch {
    // fall through to minting an in-memory-only id for the rest of this load
  }
  const minted = `anon_${randomHex16()}`;
  try {
    window.localStorage.setItem(ANON_ID_STORAGE_KEY, minted);
  } catch {
    // best-effort only
  }
  cachedAnonId = minted;
  return minted;
}

interface AnalyticsEventBody {
  event: string;
  props?: Record<string, unknown>;
  anon_id: string;
  once_key?: string;
}

/**
 * Fire-and-forget POST to `/v1/analytics/event`. Never awaited by a caller,
 * never throws, never surfaces a loading/error state — analytics must not
 * be able to affect the page it's instrumenting. Attaches the caller's own
 * Supabase bearer token when a session exists so the backend can attribute
 * the event to an account; guest sessions are real (anonymous) Supabase
 * sessions too (see AuthContext's `isGuest` doc comment), so this covers
 * guests automatically. With no session at all (the pre-auth "/" landing/
 * onboarding flow) the event is still recorded, just anonymous — the
 * backend endpoint allows both (most TRACKED_EVENTS are guest/pre-auth
 * events).
 */
function postEvent(body: AnalyticsEventBody): void {
  void (async () => {
    try {
      let accessToken: string | undefined;
      try {
        const { data } = await supabase.auth.getSession();
        accessToken = data.session?.access_token;
      } catch {
        accessToken = undefined;
      }
      await fetch(`${env.apiBaseUrl}/v1/analytics/event`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify(body),
        // Lets the request complete even if the navigation that triggered
        // it unloads this page immediately after (the common case for a
        // route-change page_view).
        keepalive: true,
      });
    } catch {
      // Best-effort telemetry only — never surfaced to the caller.
    }
  })();
}

/**
 * One call per real route change — wired from a shared navigation hook
 * (components/RouteAnalytics.tsx) in the root layout. Passes the raw
 * Next.js pathname; the backend's track_page_view already owns route-name
 * normalization (ROUTE_EVENT_MAP), so no per-page route mapping belongs
 * here on the client.
 */
export function trackPageView(route: string): void {
  const path = (route || "").trim();
  if (!path) return;
  postEvent({
    event: "page_view",
    props: { route: path, source_surface: "navigation" },
    anon_id: getOrCreateAnonId(),
  });
}

/**
 * One real feature/surface opening. `event` must already be one of
 * modules.launch_analytics.TRACKED_EVENTS' canonical names — the backend
 * no-ops on anything else (see mobile_api_service.record_analytics_event).
 *
 * `dedupe` (default true) matches how the existing module already treats
 * this shape of "<surface>_opened" event for its sibling route-opened
 * events (ROUTE_EVENT_MAP): counted once per account (+ league, when
 * `leagueId` is given), not once per remount/rerender. Pass `dedupe: false`
 * for a surface where every real instance is itself a meaningful,
 * independently-countable interaction (e.g. pqv_opened, gm_orb_opened)
 * rather than a reached-this-milestone-once signal.
 */
export function trackFeatureUse(
  event: string,
  options?: { leagueId?: string; dedupe?: boolean; props?: Record<string, unknown> },
): void {
  const name = (event || "").trim();
  if (!name) return;
  const dedupe = options?.dedupe ?? true;
  const leagueId = (options?.leagueId || "").trim();
  postEvent({
    event: name,
    props: { ...(leagueId ? { league_id: leagueId } : {}), ...(options?.props || {}) },
    anon_id: getOrCreateAnonId(),
    ...(dedupe ? { once_key: leagueId || "once" } : {}),
  });
}

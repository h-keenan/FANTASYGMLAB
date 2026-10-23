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
function postEvent(input: AnalyticsEventBody): void {
  // The hidden /design reference page renders real components with static
  // sample data and must make no API calls (analytics included).
  if (typeof window !== "undefined" && window.location?.pathname?.startsWith("/design")) return;
  // `platform` lets the founder dashboard split web vs mobile; the backend
  // also defaults a missing platform to "web".
  const body: AnalyticsEventBody = { ...input, props: { platform: "web", ...(input.props || {}) } };
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
  const trimmed = (route || "").trim();
  if (!trimmed) return;
  // Long/numeric path segments are league or user ids -- never ship them.
  const path = sanitizeRoute(trimmed);
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

/**
 * Generic "someone used feature X" event (`feature_use`), the same shape the
 * mobile client sends so the founder dashboard can combine platforms:
 * props `feature` (stable snake_case id), `action` (opened/applied/tapped/...),
 * optional `tier` ("free" | "pro"), plus caller props. Never dedupes: every
 * real interaction is countable. Never put names, ids, emails or free text in
 * props -- the backend allowlist drops unknown keys anyway.
 */
export function trackUse(
  feature: string,
  action: string = "used",
  options?: { leagueId?: string; tier?: "free" | "pro"; props?: Record<string, unknown> },
): void {
  const name = (feature || "").trim();
  if (!name) return;
  trackFeatureUse("feature_use", {
    leagueId: options?.leagueId,
    dedupe: false,
    props: {
      ...(options?.props || {}),
      feature: name,
      action,
      ...(options?.tier ? { tier: options.tier } : {}),
    },
  });
}

/** Collapse id-like path segments so a route never identifies a league/user. */
export function sanitizeRoute(path: string): string {
  const clean = (path || "").split(/[?#]/)[0];
  return clean
    .split("/")
    .map((seg) => (/^\d+$/.test(seg) || seg.length > 24 || /\d{4,}/.test(seg) ? ":id" : seg))
    .join("/")
    .slice(0, 80);
}

/** Non-sensitive error class: HTTP bucket, network, or the JS error
 * constructor name -- never the message, stack, URL or token. */
export function errorClassOf(error: unknown, status?: number): string {
  if (typeof status === "number") {
    if (status === 0) return "network";
    if (status >= 500) return "http_5xx";
    if (status >= 400) return `http_${status}`;
  }
  if (error && typeof error === "object" && "status" in error) {
    const s = (error as { status?: unknown }).status;
    if (typeof s === "number") return errorClassOf(null, s);
  }
  if (error instanceof Error && /^[A-Za-z]{2,40}$/.test(error.name)) return error.name.toLowerCase();
  return "unknown";
}

const ERROR_WINDOW_MS = 60_000;
const ERROR_MAX_PER_WINDOW = 5;
let errorWindowStart = 0;
let errorWindowCount = 0;
const seenErrorFingerprints = new Set<string>();

/** Test hook. */
export function resetErrorRateLimit(): void {
  errorWindowStart = 0;
  errorWindowCount = 0;
  seenErrorFingerprints.clear();
}

/**
 * Report a client-side failure to the backend's application_error /
 * route_error / provider_error events. Rate limited (5 per minute per tab)
 * and de-duplicated per (kind, class, route, status) so a failure loop cannot
 * flood the pipeline. Never throws.
 */
export function trackClientError(
  kind: "application_error" | "route_error" | "provider_error",
  error: unknown,
  options?: { route?: string; status?: number },
): void {
  try {
    const route = sanitizeRoute(
      options?.route ?? (typeof window !== "undefined" ? window.location.pathname : ""),
    );
    const errorClass = errorClassOf(error, options?.status);
    const fingerprint = `${kind}:${errorClass}:${route}:${options?.status ?? ""}`;
    if (seenErrorFingerprints.has(fingerprint)) return;
    const now = Date.now();
    if (now - errorWindowStart > ERROR_WINDOW_MS) {
      errorWindowStart = now;
      errorWindowCount = 0;
    }
    if (errorWindowCount >= ERROR_MAX_PER_WINDOW) return;
    errorWindowCount += 1;
    seenErrorFingerprints.add(fingerprint);
    postEvent({
      event: kind,
      props: {
        route,
        source_surface: "error",
        error_class: errorClass,
        ...(typeof options?.status === "number" ? { reason: `status_${options.status}` } : {}),
      },
      anon_id: getOrCreateAnonId(),
    });
  } catch {
    // never surfaces
  }
}

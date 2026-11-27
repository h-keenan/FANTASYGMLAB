/**
 * Copy and return-URL parsing for "Connect Yahoo" (modules/yahoo_connect.py on the API side). Pure and import-free;
 * byte-identical twin of mobile/src/lib/yahooConnect.ts so web and the app never disagree on wording.
 *
 * Flow: Connect Yahoo -> Yahoo sign-in -> API callback -> back here with `status=connected` (or `status=error&reason=`)
 * -> the user's Yahoo leagues -> pick one -> pick your team -> save.
 */

export const YAHOO_CONNECT_LABEL = "Connect Yahoo";
export const YAHOO_WHY =
  "Sign in with Yahoo once so FantasyDesk can read your Yahoo leagues. Read-only: we never see your Yahoo password and can't change your lineup. Disconnect anytime.";
export const YAHOO_UNAVAILABLE = "Connecting Yahoo isn't available right now.";
export const YAHOO_NO_LEAGUES = "We didn't find any Yahoo NFL leagues on that account for this season.";
export const YAHOO_PICK_HEADING = "Pick your Yahoo league";

/** Fallback copy for the stable `reason` codes the API sends back (the server's own `message` wins when present). */
const REASON_COPY: Record<string, string> = {
  denied: "Yahoo sign-in was cancelled. Tap Connect Yahoo to try again.",
  bad_state: "That Yahoo sign-in link expired. Tap Connect Yahoo to start again.",
  exchange_failed: "Yahoo didn't accept the sign-in. Tap Connect Yahoo to try again.",
  storage_failed: "We couldn't save your Yahoo connection. Please try again in a moment.",
  not_configured: YAHOO_UNAVAILABLE,
  not_connected: "Connect your Yahoo account first.",
  reconnect_needed: "Your Yahoo connection expired. Tap Connect Yahoo to sign in again.",
  yahoo_unavailable: "Yahoo didn't respond. Please try again in a moment.",
  yahoo_rate_limited: "Yahoo is limiting requests right now. Please try again in a minute.",
  league_not_found: "We couldn't open that Yahoo league with your account. Check that you are in it, then try again.",
  mapping_too_low: "Too few of this league's players matched FantasyDesk's player list to value it accurately.",
};

export function yahooReasonMessage(reason: string | null | undefined, message?: string | null): string {
  if (message) return message;
  return REASON_COPY[reason ?? ""] ?? "Something went wrong with Yahoo. Please try again.";
}

/** Whether the user must sign in with Yahoo again (never connected, or Yahoo refused the stored login). */
export function yahooNeedsConnect(reason: string | null | undefined): boolean {
  return reason === "not_connected" || reason === "reconnect_needed";
}

export interface YahooReturn {
  connected: boolean;
  /** Stable reason code when the round trip failed ("denied", "exchange_failed", ...). */
  reason: string;
}

/**
 * Reads where Yahoo's round trip ended. Accepts the web query (`?yahoo=connected` / `?yahoo=error&yahoo_reason=denied`)
 * and the app deep link (`fantasygmlab://yahoo?status=connected` / `?status=error&reason=denied`). Null: not a Yahoo return.
 */
export function parseYahooReturn(urlOrQuery: string | null | undefined): YahooReturn | null {
  if (!urlOrQuery) return null;
  const query = urlOrQuery.includes("?") ? urlOrQuery.slice(urlOrQuery.indexOf("?") + 1) : urlOrQuery.replace(/^\?/, "");
  const params = new URLSearchParams(query.split("#")[0]);
  const status = params.get("yahoo") ?? params.get("status");
  if (status !== "connected" && status !== "error") return null;
  return { connected: status === "connected", reason: status === "error" ? params.get("yahoo_reason") ?? params.get("reason") ?? "exchange_failed" : "" };
}

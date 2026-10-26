/**
 * First-party acquisition attribution (web only; the iOS/Android apps keep
 * analytics off). Reads utm_*, ?ref= and document.referrer once per browser,
 * keeps the FIRST touch in localStorage, and exposes it as a handful of
 * allowlisted analytics props (modules.launch_analytics.ALLOWED_PROP_KEYS)
 * plus a pending referral code to redeem when the visitor connects a league.
 * No third-party pixels, no raw URLs and no free text are ever sent.
 */

const ATTR_KEY = "fd_attribution_v1";
const REF_KEY = "fd_pending_ref";

export interface Attribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referrer_host?: string;
  has_ref?: boolean;
  click_id?: string;
}

const CLICK_ID_PARAMS: [string, string][] = [
  ["gclid", "gclid"],
  ["fbclid", "fbclid"],
  ["ttclid", "ttclid"],
  ["msclkid", "msclkid"],
  ["rdt_cid", "rdt"],
];

/** Lowercase, [a-z0-9_.-] only, max 40 chars; "" when nothing usable. */
export function cleanToken(raw: string | null | undefined): string {
  return String(raw ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_.-]/g, "")
    .slice(0, 40);
}

/** Hostname of an external referrer ("" for direct / same-site visits). */
export function referrerHost(referrer: string, ownHost: string): string {
  try {
    const host = new URL(referrer).hostname.toLowerCase().replace(/^www\./, "");
    if (!host || host === ownHost.toLowerCase().replace(/^www\./, "")) return "";
    return host.slice(0, 80);
  } catch {
    return "";
  }
}

/** Pure parser, exported for tests. */
export function parseAttribution(search: string, referrer: string, ownHost: string): Attribution & { ref?: string } {
  const params = new URLSearchParams(search);
  const out: Attribution & { ref?: string } = {};
  const source = cleanToken(params.get("utm_source"));
  const medium = cleanToken(params.get("utm_medium"));
  const campaign = cleanToken(params.get("utm_campaign"));
  if (source) out.utm_source = source;
  if (medium) out.utm_medium = medium;
  if (campaign) out.utm_campaign = campaign;
  const host = referrerHost(referrer, ownHost);
  if (host) out.referrer_host = host;
  for (const [param, label] of CLICK_ID_PARAMS) {
    if (params.get(param)) {
      out.click_id = label;
      break;
    }
  }
  const ref = (params.get("ref") || "").trim().replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64);
  if (ref) {
    out.ref = ref;
    out.has_ref = true;
  }
  return out;
}

function readStored(): Attribution | null {
  try {
    const raw = window.localStorage.getItem(ATTR_KEY);
    return raw ? (JSON.parse(raw) as Attribution) : null;
  } catch {
    return null;
  }
}

/**
 * Call once per page load (RouteAnalytics). Stores the first touch with any
 * signal, and always remembers a ?ref= code until it is redeemed.
 */
export function captureAttribution(): void {
  if (typeof window === "undefined") return;
  try {
    const parsed = parseAttribution(window.location.search, document.referrer || "", window.location.hostname);
    if (parsed.ref) window.localStorage.setItem(REF_KEY, parsed.ref);
    const { ref: _ref, ...signal } = parsed;
    void _ref;
    if (Object.keys(signal).length > 0 && !readStored()) {
      window.localStorage.setItem(ATTR_KEY, JSON.stringify(signal));
    }
  } catch {
    // storage blocked: attribution is best-effort only
  }
}

/** First-touch props to merge into analytics events ({} when none/blocked). */
export function getAttributionProps(): Attribution {
  if (typeof window === "undefined") return {};
  return readStored() ?? {};
}

export function getPendingReferralCode(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(REF_KEY) || "";
  } catch {
    return "";
  }
}

export function clearPendingReferralCode(): void {
  try {
    window.localStorage.removeItem(REF_KEY);
  } catch {
    // ignore
  }
}

/**
 * First-party acquisition attribution (web only; mobile has no UTM capture). Reads utm_*, ?ref= and
 * document.referrer, keeps the FIRST touch and the LAST touch in localStorage, and exposes them as a handful of
 * allowlisted analytics props (modules.launch_analytics.ALLOWED_PROP_KEYS)
 * plus a pending referral code to redeem when the visitor connects a league.
 * Also keeps utm_content/utm_term and the ad click id value (gclid, fbclid, ttclid, ...) so paid
 * conversions can be tied back to the ad. No third-party pixels, no raw URLs and no free text are ever sent.
 */

const ATTR_KEY = "fd_attribution_v1";
const LAST_ATTR_KEY = "fd_attribution_last_v1";
const REF_KEY = "fd_pending_ref";

export interface Attribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referrer_host?: string;
  has_ref?: boolean;
  /** Which ad network's click id was present ("gclid", "fbclid", ...). */
  click_id?: string;
  /** The click id VALUE (case-sensitive, sanitized), needed to report conversions back to the ad network. */
  click_id_value?: string;
}

/** Last-touch props ride on events under these allowlisted keys (modules.launch_analytics.ALLOWED_PROP_KEYS). */
export interface LastTouchProps {
  lt_utm_source?: string;
  lt_utm_medium?: string;
  lt_utm_campaign?: string;
  lt_referrer_host?: string;
  lt_click_id?: string;
}

const CLICK_ID_PARAMS: [string, string][] = [
  ["gclid", "gclid"],
  ["fbclid", "fbclid"],
  ["ttclid", "ttclid"],
  ["msclkid", "msclkid"],
  ["rdt_cid", "rdt"],
  ["gbraid", "gbraid"],
  ["wbraid", "wbraid"],
];

/** Click ids are case-sensitive opaque tokens: keep case, strip anything outside [A-Za-z0-9_.-], cap length. */
export function cleanClickIdValue(raw: string | null | undefined): string {
  return String(raw ?? "")
    .trim()
    .replace(/[^A-Za-z0-9_.-]/g, "")
    .slice(0, 200);
}

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
  const content = cleanToken(params.get("utm_content"));
  const term = cleanToken(params.get("utm_term"));
  if (content) out.utm_content = content;
  if (term) out.utm_term = term;
  const host = referrerHost(referrer, ownHost);
  if (host) out.referrer_host = host;
  for (const [param, label] of CLICK_ID_PARAMS) {
    const value = cleanClickIdValue(params.get(param));
    if (value) {
      out.click_id = label;
      out.click_id_value = value;
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

function readKey(key: string): Attribution | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Attribution) : null;
  } catch {
    return null;
  }
}

function readStored(): Attribution | null {
  return readKey(ATTR_KEY);
}

/**
 * A "strong" touch names a campaign or an ad click (utm_* or a click id). A referrer-only touch (just the
 * external referrer host and/or a ?ref= flag) is "weak": it must never block or displace a strong one. This was the
 * bug where a first visit from e.g. instagram.com with no UTM froze attribution, so the later paid click
 * (UTM + fbclid) was never recorded.
 */
export function isStrongTouch(a: Attribution | null | undefined): boolean {
  if (!a) return false;
  return Boolean(a.utm_source || a.utm_medium || a.utm_campaign || a.utm_content || a.utm_term || a.click_id);
}

/**
 * Our own CTAs (public SEO pages, the seasonal landing strip) tag their links utm_medium=site_cta so
 * a click can be counted. That is internal navigation, not acquisition: it may fill an empty slot but
 * must never displace a real campaign, ad click or external referrer already stored.
 */
export const SITE_CTA_MEDIUM = "site_cta";

export function isSiteCtaTouch(a: Attribution | null | undefined): boolean {
  return a?.utm_medium === SITE_CTA_MEDIUM;
}

/** Pure merge rule for the stored FIRST touch (exported for tests). */
export function nextFirstTouch(stored: Attribution | null, incoming: Attribution): Attribution {
  if (!stored || Object.keys(stored).length === 0) return incoming;
  if (isSiteCtaTouch(incoming)) return stored;
  if (!isStrongTouch(stored) && isStrongTouch(incoming)) return incoming; // upgrade weak -> strong
  return stored;
}

/** Pure rule for the stored LAST touch: latest strong touch wins; a weak referrer only replaces a weak/absent one. */
export function nextLastTouch(stored: Attribution | null, incoming: Attribution): Attribution {
  if (!stored || Object.keys(stored).length === 0) return incoming;
  if (isSiteCtaTouch(incoming)) return stored;
  if (isStrongTouch(incoming)) return incoming;
  if (isStrongTouch(stored)) return stored;
  return incoming;
}

/**
 * Call once per page load (RouteAnalytics). Stores the first touch with any
 * signal (a later UTM/click-id touch upgrades a referrer-only first touch), the last touch
 * (latest campaign/ad touch), and always remembers a ?ref= code until it is redeemed.
 */
export function captureAttribution(): void {
  if (typeof window === "undefined") return;
  try {
    const parsed = parseAttribution(window.location.search, document.referrer || "", window.location.hostname);
    if (parsed.ref) window.localStorage.setItem(REF_KEY, parsed.ref);
    const { ref: _ref, ...signal } = parsed;
    void _ref;
    if (Object.keys(signal).length === 0) return;
    const first = nextFirstTouch(readStored(), signal);
    window.localStorage.setItem(ATTR_KEY, JSON.stringify(first));
    window.localStorage.setItem(LAST_ATTR_KEY, JSON.stringify(nextLastTouch(readKey(LAST_ATTR_KEY), signal)));
  } catch {
    // storage blocked: attribution is best-effort only
  }
}

/** Last-touch props (lt_*) from the latest campaign/referrer touch; never carries the click id VALUE. */
export function getLastTouchProps(): LastTouchProps {
  if (typeof window === "undefined") return {};
  const last = readKey(LAST_ATTR_KEY);
  if (!last) return {};
  const out: LastTouchProps = {};
  if (last.utm_source) out.lt_utm_source = last.utm_source;
  if (last.utm_medium) out.lt_utm_medium = last.utm_medium;
  if (last.utm_campaign) out.lt_utm_campaign = last.utm_campaign;
  if (last.referrer_host) out.lt_referrer_host = last.referrer_host;
  if (last.click_id) out.lt_click_id = last.click_id;
  return out;
}

/** First-touch props plus last-touch (lt_*) props to merge into analytics events ({} when none/blocked). */
export function getAttributionProps(): Attribution & LastTouchProps {
  if (typeof window === "undefined") return {};
  return { ...(readStored() ?? {}), ...getLastTouchProps() };
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

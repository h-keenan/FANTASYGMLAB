/**
 * No-signup "try" links for ads: /try/<topic> opens the REAL feature on shared sample/demo data and ends in ONE
 * "Do this for your league" CTA into connect-league. Mobile twin: mobile/src/lib/tryDeepLink.ts
 * (fantasygmlab://try/<topic>). The advertising API hands out the matching absolute URLs
 * (modules/external_ad_api.py try_url; utm_source=ad_app, caller utm_* passed through).
 *
 * Attribution rule: a visitor arriving with utm params and click ids gets them stored as first/last touch by RouteAnalytics
 * (lib/attribution.ts) on this page; the CTA re-attaches the same params so the touch also survives a storage-blocked
 * browser. With no campaign params at all the CTA adds utm_medium=site_cta tags, which never displace a real touch.
 */

import { withUtm } from "@/lib/seasonalLanding";

export type TryTopic = "start-sit" | "trade" | "waivers" | "playoffs" | "dynasty-values";

export interface TryTopicInfo {
  topic: TryTopic;
  path: string;
  /** Page <h1>. */
  title: string;
  intro: string;
  /** Where the real feature lives for a connected user (documentation + metadata canonical). */
  realFeaturePath: string;
}

export const TRY_BASE_PATH = "/try";
export const TRY_CONNECT_PATH = "/connect-league";
export const TRY_CTA_LABEL = "Do this for your league";

export const TRY_TOPICS: readonly TryTopicInfo[] = [
  {
    topic: "start-sit",
    path: "/try/start-sit",
    title: "Start/sit: who goes in your lineup",
    intro: "A real suggested lineup move on an example league: who to start, who to sit, and the typical-week range behind it.",
    realFeaturePath: "/matchup",
  },
  {
    topic: "trade",
    path: "/try/trade",
    title: "Trade check: is this offer fair?",
    intro: "A realistic dynasty trade is already loaded into the real trade analyzer. Change any player to test your own.",
    realFeaturePath: "/trade-analyzer",
  },
  {
    topic: "waivers",
    path: "/try/waivers",
    title: "Waiver pickup: who to add",
    intro: "The real waiver board on an example league: priority adds, why each fits, and a bid range.",
    realFeaturePath: "/waivers",
  },
  {
    topic: "playoffs",
    path: "/try/playoffs",
    title: "Fantasy playoff schedule by position",
    intro: "Which teams get the softest and toughest defenses through the fantasy playoff weeks.",
    realFeaturePath: "/fantasy-playoff-strength-of-schedule",
  },
  {
    topic: "dynasty-values",
    path: "/try/dynasty-values",
    title: "Dynasty values: what players are worth",
    intro: "The dynasty trade value chart for 1QB and Superflex leagues, updated daily.",
    realFeaturePath: "/dynasty-trade-value-chart",
  },
];

export function isTryTopic(value: string): value is TryTopic {
  return TRY_TOPICS.some((t) => t.topic === value);
}

export function tryTopicInfo(topic: TryTopic): TryTopicInfo {
  return TRY_TOPICS.find((t) => t.topic === topic) as TryTopicInfo;
}

/** Acquisition params carried from the try page into the CTA link (same set lib/attribution.ts understands). */
const CARRY_PARAMS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "ref",
  "gclid",
  "fbclid",
  "ttclid",
  "msclkid",
  "rdt_cid",
  "gbraid",
  "wbraid",
] as const;

/**
 * The single CTA target: /connect-league with the page's own campaign/click-id params preserved verbatim. With none
 * present, internal site_cta tags (utm_source=try, utm_campaign=<topic>) are added.
 */
export function tryCtaHref(topic: TryTopic, search: string): string {
  const incoming = new URLSearchParams(search);
  const carried = new URLSearchParams();
  for (const key of CARRY_PARAMS) {
    const value = incoming.get(key);
    if (value) carried.set(key, value);
  }
  if ([...carried.keys()].some((k) => k !== "ref")) {
    const query = carried.toString();
    return `${TRY_CONNECT_PATH}?${query}`;
  }
  const tagged = withUtm(TRY_CONNECT_PATH, "try", topic.replace(/-/g, "_"), "try_cta");
  const ref = carried.get("ref");
  return ref ? `${tagged}&ref=${encodeURIComponent(ref)}` : tagged;
}

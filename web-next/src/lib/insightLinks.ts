/**
 * THE map from "a fact the app states about your league/team" to the one place
 * that explains or acts on it. Every tappable stat tile, insight card and chip
 * resolves its destination here, so a stat can never be added without
 * deciding where it goes, and web and the app can never disagree.
 *
 * Byte-identical twin: mobile/src/lib/insightLinks.ts (scripts/check_lib_twins.mjs).
 * Platform-neutral on purpose (no imports): this file says WHICH page and
 * section; each platform's adapter turns that into a URL (web-next/src/lib/
 * insightHref.ts) or a navigation call (mobile/src/lib/insightNav.ts).
 */

export type InsightKey =
  | "record"
  | "power"
  | "franchise"
  | "draft_capital"
  | "future_capital"
  | "starter"
  | "bench"
  | "age"
  | "injury"
  | "strategy"
  | "position_room"
  | "league_activity"
  | "survival";

/** The league rank boards (League Rankings page / app Teams screen). */
export type RankBoardMetric = "power" | "franchise" | "draft_capital" | "starter" | "bench" | "age";

export interface InsightTarget {
  /** Web route segment (also the app screen's family): see navCatalog.ts. */
  page: "league-rankings" | "alerts" | "my-team" | "gm-plan" | "league-recaps";
  /** League Rankings only: which rank board to land on. */
  metric?: RankBoardMetric;
  /** Page section to scroll to (web `#anchor`); the app opens the matching tab/section. */
  section?: string;
  /** Verb phrase read after the stat by screen readers: "Avg Age 26.1, open League Rankings". */
  label: string;
}

export const INSIGHT_TARGETS: Record<InsightKey, InsightTarget> = {
  record: { page: "league-rankings", section: "your-standing", label: "open your league standing" },
  power: { page: "league-rankings", metric: "power", label: "open the Roster Power rankings" },
  franchise: { page: "league-rankings", metric: "franchise", label: "open the Franchise Value rankings" },
  draft_capital: { page: "league-rankings", metric: "draft_capital", label: "open the Draft Capital rankings" },
  future_capital: { page: "league-rankings", metric: "draft_capital", label: "open the Draft Capital rankings" },
  starter: { page: "league-rankings", metric: "starter", label: "open the Starter Quality rankings" },
  bench: { page: "league-rankings", metric: "bench", label: "open the Bench Depth rankings" },
  age: { page: "league-rankings", metric: "age", label: "open the Roster Age rankings" },
  injury: { page: "alerts", label: "open Alerts" },
  strategy: { page: "gm-plan", label: "open your GM Plan" },
  position_room: { page: "my-team", section: "team-analysis-heading", label: "open Team Analysis on My Team" },
  league_activity: { page: "league-recaps", label: "open League Recaps" },
  survival: { page: "league-rankings", metric: "power", label: "open the league rankings" },
};

export function insightTarget(key: InsightKey): InsightTarget {
  return INSIGHT_TARGETS[key];
}

/** Anchor id of a rank board on the League Rankings page. */
export function rankBoardAnchor(metric: RankBoardMetric): string {
  return `board-${metric}`;
}

/** The anchor (without `#`) a web link should land on, or null for the page top. */
export function insightAnchor(key: InsightKey): string | null {
  const target = INSIGHT_TARGETS[key];
  if (target.metric) return rankBoardAnchor(target.metric);
  return target.section ?? null;
}

/** Screen-reader name for a tappable stat: "Avg Age 26.1, League avg 25.2, open the Roster Age rankings". */
export function insightAriaLabel(key: InsightKey, parts: ReadonlyArray<string | null | undefined>): string {
  const spoken = parts.filter((part): part is string => Boolean(part && part.trim())).join(", ");
  return `${spoken}, ${INSIGHT_TARGETS[key].label}`;
}

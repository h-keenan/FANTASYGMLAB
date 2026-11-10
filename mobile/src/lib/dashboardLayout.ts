/**
 * Dashboard information hierarchy, shared by web and the app. The block
 * between the SHARED markers is byte-identical to
 * web-next/src/lib/dashboardLayout.ts (a mobile test compares them): edit both
 * together. Pure TS, no imports, so node --test can run it. See
 * docs/dashboard-reorg.md for the rationale.
 */

// SHARED BEGIN
/** Top-to-bottom module order of the logged-in Dashboard, on every platform. */
export const DASHBOARD_MODULE_ORDER = [
  "start_here", // first-run checklist (new accounts only, dismissible)
  "now", // "At a glance" strip: lineup, trade deadline, alerts, waivers
  "needs_attention", // compact urgent list (see buildNeedsAttention), links out
  "next_moves", // "This week": the rest of this week's actions
  "trades", // one line: "N trade ideas -> Trade Hub" (cards live on GM Plan / Trade Hub)
  "my_team", // record / ranks / strengths / injuries in one section
  "alerts_waivers", // news and waivers that affect my players
  "more", // collapsed: league activity, recap, matchup, quick actions, league type, games
] as const;

export type DashboardModuleKey = (typeof DASHBOARD_MODULE_ORDER)[number];

export interface DashboardTradeWindow {
  trade_deadline_week: number | null;
  current_week: number | null;
  trade_deadline_passed: boolean;
}

export interface DashboardNowRow {
  key: string;
  status: string;
  tone: string;
}

export interface DashboardNowChip {
  key: "lineup" | "deadline" | "alerts" | "waivers";
  label: string;
  value: string;
  tone: "positive" | "risk" | "waiver" | "neutral";
  route: "matchup" | "trade_hub" | "alerts" | "waivers";
}

/**
 * "Weeks left" is the difference between Sleeper's real trade-deadline week and
 * its current week. Null when the league has no deadline, it has passed, or
 * the server did not send the window (never guessed).
 */
export function deadlineChip(window: DashboardTradeWindow | null | undefined): DashboardNowChip | null {
  if (!window || window.trade_deadline_passed) return null;
  const deadline = window.trade_deadline_week;
  if (deadline === null || deadline === undefined) return null;
  const current = window.current_week;
  let value = `Week ${deadline}`;
  if (current !== null && current !== undefined && current <= deadline) {
    const left = deadline - current;
    value = left === 0 ? `This week (Wk ${deadline})` : `${left} wk${left === 1 ? "" : "s"} left (Wk ${deadline})`;
  }
  return {
    key: "deadline",
    label: "Trade deadline",
    value,
    tone: current !== null && current !== undefined && deadline - current <= 1 ? "risk" : "neutral",
    route: "trade_hub",
  };
}

/** The "what matters now" chips, in priority order. Only real data; empty chips are omitted. */
export function buildNowChips(
  rows: DashboardNowRow[] | null | undefined,
  tradeWindow: DashboardTradeWindow | null | undefined,
  alertCount: number,
  /** Chip keys already shown in "Needs attention" (so nothing shows twice). */
  exclude: readonly string[] = [],
): DashboardNowChip[] {
  const chips: DashboardNowChip[] = [];
  const lineup = (rows ?? []).find((row) => row.key === "lineup");
  if (lineup && !exclude.includes("lineup")) {
    chips.push({
      key: "lineup",
      label: "Lineup",
      value: lineup.status,
      tone: lineup.tone === "risk" ? "risk" : lineup.tone === "positive" ? "positive" : "neutral",
      route: "matchup",
    });
  }
  const deadline = deadlineChip(tradeWindow);
  if (deadline && !exclude.includes("deadline")) chips.push(deadline);
  if (alertCount > 0) {
    chips.push({
      key: "alerts",
      label: "Alerts",
      value: `${alertCount} to watch`,
      tone: "risk",
      route: "alerts",
    });
  }
  const waiver = (rows ?? []).find((row) => row.key === "waiver");
  if (waiver) {
    chips.push({ key: "waivers", label: "Waivers", value: waiver.status, tone: "waiver", route: "waivers" });
  }
  return chips;
}

/**
 * Rows the "Next moves" list still shows: the trade row lives in the Trades
 * block, and a lineup row that only says "set" lives in the Now strip.
 */
export function nextMoveRowFilter(row: DashboardNowRow): boolean {
  if (row.key === "trade") return false;
  if (row.key === "lineup" && row.tone !== "risk") return false;
  return true;
}

/** True when a dashboard item carries a real trade package. */
export function isTradeItem(item: { presentation?: { trade_package?: unknown } | null }): boolean {
  return Boolean(item.presentation && item.presentation.trade_package);
}

export interface DashboardAttentionRow extends DashboardNowRow {
  headline: string;
  why: string;
}

export interface DashboardAttentionItem {
  headline: string;
  reason: string;
  destination: string;
  presentation?: { trade_package?: unknown } | null;
}

export interface DashboardAttentionEntry<T extends DashboardAttentionItem = DashboardAttentionItem> {
  /** "lineup" and "deadline" match the Now chip keys; "item" is a server top-priority tile. */
  source: "lineup" | "deadline" | "item";
  badge: string;
  headline: string;
  why: string;
  /** Where it opens: Matchup (lineup), GM Plan (deadline), or the item's own destination. */
  target: "matchup" | "gm_plan" | "item";
  item?: T;
}

export const NEEDS_ATTENTION_LIMIT = 3;

/**
 * The compact "Needs attention" list. No new scoring: "urgent" is read only
 * from fields the Dashboard response already has, in this order:
 *   1. a lineup row the server marked tone "risk" (an out/injured starter),
 *   2. a trade deadline this week or next (deadlineChip's own risk tone),
 *   3. the server's own top-priority, non-trade tiles (category top_priority).
 * Capped at NEEDS_ATTENTION_LIMIT; the full list stays on GM Plan.
 */
export function buildNeedsAttention<T extends DashboardAttentionItem>(
  rows: DashboardAttentionRow[] | null | undefined,
  tradeWindow: DashboardTradeWindow | null | undefined,
  topPriorityItems: T[],
): DashboardAttentionEntry<T>[] {
  const out: DashboardAttentionEntry<T>[] = [];
  const lineup = (rows ?? []).find((row) => row.key === "lineup" && row.tone === "risk");
  if (lineup) {
    out.push({ source: "lineup", badge: lineup.status || "Lineup", headline: lineup.headline, why: lineup.why, target: "matchup" });
  }
  const deadline = deadlineChip(tradeWindow);
  if (deadline && deadline.tone === "risk") {
    out.push({
      source: "deadline",
      badge: "Deadline",
      headline: `Trade deadline: ${deadline.value}`,
      why: "Trades lock after the deadline. Review your plan before then.",
      target: "gm_plan",
    });
  }
  for (const item of topPriorityItems) {
    if (item.presentation && item.presentation.trade_package) continue; // trade ideas live in Trade Hub
    out.push({ source: "item", badge: "Top priority", headline: item.headline, why: item.reason, target: "item", item });
  }
  return out.slice(0, NEEDS_ATTENTION_LIMIT);
}

/** Rows "This week" still shows once Needs attention has taken its own. */
export function weekRowsAfterAttention<R extends DashboardNowRow & { headline?: string }>(
  rows: R[],
  attention: { source: string; headline?: string }[],
): R[] {
  const lineupTaken = attention.some((entry) => entry.source === "lineup");
  const taken = new Set(attention.map((entry) => normalizeAlertTitle(entry.headline)).filter(Boolean));
  return rows.filter(
    (row) => nextMoveRowFilter(row) && !(lineupTaken && row.key === "lineup") && !taken.has(normalizeAlertTitle(row.headline)),
  );
}

/** Case/punctuation/"(+N more)"-insensitive alert title, so the same alert never shows in two modules. */
export function normalizeAlertTitle(title: string | null | undefined): string {
  return (title ?? "")
    .toLowerCase()
    .replace(/\(\+\d+ more\)/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Items still worth listing once Needs attention has taken its own (same object or same normalized title). */
export function itemsAfterAttention<T extends { headline: string }>(items: T[], attention: { item?: T; headline?: string }[]): T[] {
  const taken = new Set(attention.map((entry) => normalizeAlertTitle(entry.headline)).filter(Boolean));
  return items.filter((item) => !attention.some((entry) => entry.item === item) && !taken.has(normalizeAlertTitle(item.headline)));
}

/** The Dashboard's one-line trade pointer: a count and a link, never idea cards. */
export function tradeIdeasLine(count: number, deadlinePassed: boolean, pending: boolean): string {
  if (deadlinePassed) return TRADES_BLOCK_COPY.deadlinePassed;
  if (pending) return "Checking for trade ideas...";
  if (count <= 0) return TRADES_BLOCK_COPY.empty;
  return `${count} trade idea${count === 1 ? "" : "s"}`;
}

export const TRADES_BLOCK_COPY = {
  title: "Trade ideas",
  link: "Trade Hub",
  analyze: "Analyze a trade",
  more: "More trade ideas",
  empty: "No trade idea stands out right now.",
  deadlinePassed: "Trade deadline has passed; trades reopen after the season.",
  beginnerExplainer:
    "A trade idea shows who you give, who you get, and whether the value works out for you. Nothing happens until you send it in Sleeper.",
  goalLine: {
    win_now: "Tuned for winning this season.",
    rebuilding: "Tuned for building future value.",
    exploring: "",
  },
} as const;

export function tradesGoalLine(goal: string | null | undefined): string {
  return goal === "win_now" || goal === "rebuilding" || goal === "exploring" ? TRADES_BLOCK_COPY.goalLine[goal] : "";
}

/** Beginner tiers get short explainers; veterans get the call and the numbers only. */
export function dashboardShowsExplanations(level: string | null | undefined): boolean {
  return level === "new_to_fantasy" || level === "beginner";
}
// SHARED END

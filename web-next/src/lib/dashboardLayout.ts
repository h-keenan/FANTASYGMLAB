/**
 * Dashboard information hierarchy, shared by web and the app. The block
 * between the SHARED markers is byte-identical to
 * mobile/src/lib/dashboardLayout.ts (a mobile test compares them): edit both
 * together. Pure TS, no imports, so node --test can run it. See
 * docs/dashboard-reorg.md for the rationale.
 */

// SHARED BEGIN
/** Top-to-bottom module order of the logged-in Dashboard, on every platform. */
export const DASHBOARD_MODULE_ORDER = [
  "start_here", // first-run checklist (new accounts only, dismissible)
  "now", // "what matters now" strip: lineup, trade deadline, alerts, waivers
  "trades", // primary block: best trade idea + Analyze a trade
  "next_moves", // other urgent actions (lineup risk, waiver, offseason next step)
  "my_team", // record / ranks / strengths / injuries in one section
  "alerts_waivers", // news and waivers that affect my players
  "league_pulse", // league activity
  "more", // collapsed: recap, matchup, quick actions, league type, games
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
): DashboardNowChip[] {
  const chips: DashboardNowChip[] = [];
  const lineup = (rows ?? []).find((row) => row.key === "lineup");
  if (lineup) {
    chips.push({
      key: "lineup",
      label: "Lineup",
      value: lineup.status,
      tone: lineup.tone === "risk" ? "risk" : lineup.tone === "positive" ? "positive" : "neutral",
      route: "matchup",
    });
  }
  const deadline = deadlineChip(tradeWindow);
  if (deadline) chips.push(deadline);
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

export const TRADES_BLOCK_COPY = {
  title: "Trades",
  analyze: "Analyze a trade",
  more: "More trade ideas",
  empty: "No trade idea stands out right now. Check any offer you get, or browse the board.",
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

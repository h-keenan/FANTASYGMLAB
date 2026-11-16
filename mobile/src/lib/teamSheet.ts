/**
 * The team sheet's shared, data-driven model. The Fantasy Sim team sheet and the
 * Desk (real Sleeper) team sheet both render through TeamSheet*; each only maps
 * its own payload into these shapes. Pure and platform-free: byte-identical in
 * web-next and mobile (scripts/check_lib_twins.mjs).
 */

export type TeamSheetLevel = "strength" | "solid" | "need" | "ok";

export interface TeamSheetPosition {
  pos: string;
  level: TeamSheetLevel;
  rank: number;
  teams: number;
  depth: number;
}

export interface TeamSheetTile {
  label: string;
  value: string;
}

export interface TeamSheetChip {
  label: string;
  tone: "accent" | "premium" | "success" | "muted";
}

export function teamSheetLevelLabel(level: TeamSheetLevel): string {
  return level === "strength" ? "Strength" : level === "need" ? "Need" : "Solid";
}

export function teamSheetLevelTone(level: TeamSheetLevel): "success" | "danger" | "muted" {
  return level === "strength" ? "success" : level === "need" ? "danger" : "muted";
}

/** "#3 of 12 · depth 2". */
export function teamSheetPositionLine(p: Pick<TeamSheetPosition, "rank" | "teams" | "depth">): string {
  return `#${p.rank} of ${p.teams} · depth ${p.depth}`;
}

/** "Strong at RB, WR. Needs TE." (empty when nothing stands out). */
export function teamSheetStrengthNeedLine(strengths: string[] | undefined, needs: string[] | undefined): string {
  const parts: string[] = [];
  if (strengths?.length) parts.push(`Strong at ${strengths.join(", ")}.`);
  if (needs?.length) parts.push(`Needs ${needs.join(", ")}.`);
  return parts.join(" ");
}

/** "Week 13 vs Rival FC" (empty without a game). */
export function teamSheetNextGameLine(game: { week: number; opponent: string } | null | undefined): string {
  return game ? `Week ${game.week} vs ${game.opponent}` : "";
}

/** W-streaks read green, anything else red. */
export function teamSheetStreakTone(streak: string | null | undefined): "success" | "danger" {
  return (streak ?? "").startsWith("W") ? "success" : "danger";
}

export function teamSheetPoints(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "-" : value.toFixed(1);
}

/** One manager tendency signal as the trade-style read needs it. */
export interface TradeStyleSignal {
  status?: string;
  label?: string | null;
  summary?: string | null;
}

// Most distinctive read first (mirrors the headline order in modules.manager_tendencies).
const TRADE_STYLE_TAGS: Array<[string, string, string]> = [
  ["trade_frequency", "trades_more_than_most", "TRADE HAPPY"],
  ["trade_frequency", "trades_less_than_most", "SELECTIVE"],
  ["posture", "contending", "CONTENDER"],
  ["posture", "rebuilding", "REBUILDER"],
  ["pick_behavior", "buys_picks", "PICK HOARDER"],
  ["pick_behavior", "sells_picks", "PICK SELLER"],
  ["package_shape", "consolidates", "CONSOLIDATOR"],
  ["age_preference", "acquires_younger", "YOUTH MOVER"],
  ["age_preference", "acquires_older", "VETERAN BUYER"],
];

/**
 * The trade-style tag and one-line description from a manager's REAL tendency
 * signals (GET .../managers/{id}/tendencies). Presentation only: the labels and
 * summaries are the server's; nothing is scored here. Null when no signal has
 * enough trades to name a style.
 */
export function tradeStyleFromSignals(
  signals: Record<string, TradeStyleSignal | undefined> | null | undefined,
): { tag: string; blurb: string } | null {
  if (!signals) return null;
  for (const [key, label, tag] of TRADE_STYLE_TAGS) {
    const s = signals[key];
    if (s?.status === "ok" && s.label === label) return { tag, blurb: s.summary ?? "" };
  }
  return null;
}

/** "9-3 · 2nd of 12" style season line for the History tab. */
export function teamSheetSeasonLine(s: { wins: number; losses: number; ties: number; place: number | null; of: number }): string {
  const rec = s.ties ? `${s.wins}-${s.losses}-${s.ties}` : `${s.wins}-${s.losses}`;
  return s.place ? `${rec} · #${s.place} of ${s.of}` : rec;
}

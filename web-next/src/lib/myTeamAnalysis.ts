/**
 * My Team's Team Analysis rows and Roster Composition split. Pure helpers:
 * the room statuses come from GET .../my-team-needs (via
 * buildPositionGroupItems) and the composition from each roster player's
 * own `score`, so nothing here is invented.
 */

import { sumScore, type PositionGroupItem } from "./myTeamPresentation";

export type AnalysisTone = "success" | "warning" | "danger" | "information";

export interface TeamAnalysisRow {
  position: string;
  /** Short status phrase shown on the collapsed row. */
  status: string;
  tone: AnalysisTone;
  /** The full sentence, shown only when the row is expanded. */
  body: string;
}

const ANALYSIS_STATUS: Record<string, { status: string; tone: AnalysisTone }> = {
  Strength: { status: "Strength", tone: "success" },
  Thin: { status: "Thin", tone: "danger" },
  "Future risk": { status: "Future risk", tone: "danger" },
  "Upgrade room": { status: "Upgrade opportunity", tone: "warning" },
  "Injury pressure": { status: "Injury pressure", tone: "warning" },
  Covered: { status: "Covered", tone: "information" },
};

const ANALYSIS_ORDER = ["QB", "RB", "WR", "TE"];

/** One Team Analysis row per position room, QB/RB/WR/TE first. */
export function buildTeamAnalysisRows(items: PositionGroupItem[]): TeamAnalysisRow[] {
  const rank = (position: string) => {
    const index = ANALYSIS_ORDER.indexOf(position);
    return index === -1 ? ANALYSIS_ORDER.length : index;
  };
  return items
    .map((item) => {
      const meta = ANALYSIS_STATUS[item.label] ?? { status: item.label, tone: "information" as AnalysisTone };
      return { position: item.position, status: meta.status, tone: meta.tone, body: item.body };
    })
    .sort((a, b) => rank(a.position) - rank(b.position));
}

export interface CompositionSegment {
  key: string;
  label: string;
  value: number;
  /** Whole-number percent; the segments always add to exactly 100. */
  percent: number;
}

/** Value split across roster groups, computed from each player's `score`.
 * Groups with no value are dropped (no IR/taxi: nothing to draw). Percents
 * use largest-remainder rounding so the legend sums to 100. */
export function buildRosterComposition(
  groups: { key: string; label: string; players: { score: number | null }[] }[],
): CompositionSegment[] {
  const sized = groups
    .map((group) => ({ key: group.key, label: group.label, value: sumScore(group.players) }))
    .filter((group) => group.value > 0);
  const total = sized.reduce((sum, group) => sum + group.value, 0);
  if (total <= 0) return [];
  const raw = sized.map((group) => (group.value / total) * 100);
  const percents = raw.map((r) => Math.floor(r));
  let remaining = 100 - percents.reduce((sum, p) => sum + p, 0);
  const byRemainder = raw.map((r, index) => ({ index, remainder: r - Math.floor(r) })).sort((a, b) => b.remainder - a.remainder);
  for (const { index } of byRemainder) {
    if (remaining <= 0) break;
    percents[index] += 1;
    remaining -= 1;
  }
  return sized.map((group, index) => ({ ...group, percent: percents[index] }));
}

/**
 * The Matchup page as templates (docs/ui-patterns.md "Module templates"): the pure model that turns the matchup read
 * into one Hero (win odds + score) and the collapsed summaries of its CompactModules (Insights, Teams & values,
 * Lineup comparison, Suggested moves). Import-light, byte-identical twin of mobile/src/lib/matchupModules.ts.
 */
import type { CompactPart, CompactTone } from "./compactModule";

export interface MatchupEdgeInput {
  position: string;
  edge: number;
}

export interface MatchupHeroInput {
  week: number | null;
  myName: string;
  opponentName: string;
  /** Live/final points; null before any game starts. */
  myScore: number | null;
  opponentScore: number | null;
  myProjected: number | null;
  opponentProjected: number | null;
  /** My win chance, 0-100, null when not modeled. */
  winPercent: number | null;
  kickedOff: boolean;
  live: boolean;
  final: boolean;
}

export interface MatchupHeroModel {
  label: string;
  value: string;
  context: string;
  tone: "success" | "danger" | "accent";
}

function fixed(n: number | null | undefined): string | null {
  return typeof n === "number" && Number.isFinite(n) ? n.toFixed(1) : null;
}

export function signedPoints(n: number): string {
  if (Math.abs(n) < 0.05) return "0.0";
  return `${n > 0 ? "+" : "-"}${Math.abs(n).toFixed(1)}`;
}

/** One big number: win chance when modeled, else the score (live/final), else the projections. Context names both teams. */
export function matchupHeroModel(input: MatchupHeroInput): MatchupHeroModel {
  const state = input.final ? "Final" : input.live ? "Live" : null;
  const score = input.kickedOff ? `${fixed(input.myScore) ?? "0.0"} - ${fixed(input.opponentScore) ?? "0.0"}` : null;
  const proj =
    fixed(input.myProjected) && fixed(input.opponentProjected) ? `Proj ${fixed(input.myProjected)} - ${fixed(input.opponentProjected)}` : null;
  const context = [`vs ${input.opponentName}`, score, proj].filter(Boolean).join(" · ");
  const label = [state, input.winPercent != null ? "Win chance" : "Matchup"].filter(Boolean).join(" · ");
  if (input.winPercent != null) {
    const tone = input.winPercent >= 55 ? "success" : input.winPercent <= 45 ? "danger" : "accent";
    return { label, value: `${Math.round(input.winPercent)}%`, context, tone };
  }
  if (score) return { label, value: score, context: [`vs ${input.opponentName}`, proj].filter(Boolean).join(" · "), tone: "accent" };
  return { label, value: proj ? proj.replace("Proj ", "") : "-", context: `vs ${input.opponentName}`, tone: "accent" };
}

export interface EdgeChip {
  position: string;
  label: string;
  tone: "success" | "danger" | "muted";
}

/** Position edges as chips, biggest swing first ("RB +16.7"). */
export function edgeChips(edges: ReadonlyArray<MatchupEdgeInput> | null | undefined): EdgeChip[] {
  return [...(edges ?? [])]
    .sort((a, b) => Math.abs(b.edge) - Math.abs(a.edge))
    .map((e) => ({
      position: e.position,
      label: `${e.position} ${signedPoints(e.edge)}`,
      tone: Math.abs(e.edge) < 0.05 ? "muted" : e.edge > 0 ? "success" : "danger",
    }));
}

/** Insights collapsed: the verdict, the best edge and the worst edge ("You're favored · RB +16.7 · WR -4.6"). */
export function insightsParts(headline: string, tone: CompactTone, edges: ReadonlyArray<MatchupEdgeInput> | null | undefined): CompactPart[] {
  const sorted = [...(edges ?? [])].sort((a, b) => b.edge - a.edge);
  const best = sorted[0];
  const worst = sorted.length > 1 ? sorted[sorted.length - 1] : null;
  const parts: Array<CompactPart | null> = [
    { key: "verdict", text: headline.replace(/\.$/, ""), tone, strong: true },
    best && best.edge >= 0.05 ? { key: "best", text: `${best.position} ${signedPoints(best.edge)}`, tone: "success" as const } : null,
    worst && worst.edge <= -0.05 ? { key: "worst", text: `${worst.position} ${signedPoints(worst.edge)}`, tone: "danger" as const } : null,
  ];
  return parts.filter((p): p is CompactPart => p != null);
}

/** Teams and values collapsed: "Value 45,719 vs 48,673 · -2,954 · Proj margin +8.6". */
export function teamsValuesParts(input: {
  myValue: string;
  opponentValue: string;
  valueMargin: string;
  edge: "you" | "opponent" | "even" | string;
  projectedMargin: number | null;
}): CompactPart[] {
  const tone: CompactTone = input.edge === "you" ? "success" : input.edge === "opponent" ? "danger" : "muted";
  const parts: Array<CompactPart | null> = [
    { key: "value", text: `Value ${input.myValue} vs ${input.opponentValue}` },
    { key: "margin", text: input.valueMargin, tone },
    input.projectedMargin != null
      ? { key: "proj", text: `Proj margin ${signedPoints(input.projectedMargin)}`, tone: input.projectedMargin >= 0.05 ? ("success" as const) : input.projectedMargin <= -0.05 ? ("danger" as const) : ("muted" as const) }
      : null,
  ];
  return parts.filter((p): p is CompactPart => p != null);
}

/** Lineup comparison collapsed: "Suggested 118.3 vs 109.7 · +8.6 · 9 slots". */
export function lineupParts(input: {
  view: "suggested" | "actual";
  mineTotal: number | null;
  opponentTotal: number | null;
  slotCount: number;
  bestBall?: boolean;
}): CompactPart[] {
  if (input.slotCount === 0) return [{ key: "none", text: "No lineups posted for this week yet", tone: "muted" }];
  const m = fixed(input.mineTotal);
  const o = fixed(input.opponentTotal);
  const margin = input.mineTotal != null && input.opponentTotal != null ? input.mineTotal - input.opponentTotal : null;
  const parts: Array<CompactPart | null> = [
    { key: "view", text: input.bestBall ? "Best ball" : input.view === "actual" ? "Actual" : "Suggested" },
    m && o ? { key: "totals", text: `${m} vs ${o}`, strong: true } : null,
    margin != null ? { key: "margin", text: signedPoints(margin), tone: margin >= 0.05 ? ("success" as const) : margin <= -0.05 ? ("danger" as const) : ("muted" as const) } : null,
    { key: "slots", text: `${input.slotCount} slots` },
  ];
  return parts.filter((p): p is CompactPart => p != null);
}

/** Suggested moves collapsed: "3 moves · Start Gibbs +4.2 pts". */
export function movesParts(moves: ReadonlyArray<{ startName: string; gain: number | null }> | null): CompactPart[] {
  if (moves === null) return [{ key: "wait", text: "Appear once Sleeper has your lineup", tone: "muted" }];
  if (moves.length === 0) return [{ key: "none", text: "Your lineup already matches ours", tone: "success" }];
  const top = [...moves].sort((a, b) => (b.gain ?? -Infinity) - (a.gain ?? -Infinity))[0];
  return [
    { key: "count", text: `${moves.length} move${moves.length === 1 ? "" : "s"}`, strong: true },
    { key: "top", text: top.gain != null ? `Start ${top.startName} ${signedPoints(top.gain)} pts` : `Start ${top.startName}`, tone: top.gain != null && top.gain >= 0.05 ? "success" : "muted" },
  ];
}

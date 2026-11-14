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

// ---------------------------------------------------------------------------------------------------------------------
// Matchup hero card (V1) and ticker. The same model feeds the FantasyDesk Matchup page, the Fantasy Sim Home card and
// the compact ticker on stacks. Structural inputs only; the sim adapter never carries a rating, only projection range.
// ---------------------------------------------------------------------------------------------------------------------

export interface MatchupSwingInput {
  playerId: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier?: string | null;
  /** The projection's low / high for the week (the sim's floor / ceiling). */
  low: number | null;
  high: number | null;
  /** His game is over (or he cannot play): nothing left to swing. */
  done: boolean;
  side: "mine" | "opponent";
}

export interface MatchupSwingPlayer {
  key: string;
  side: "mine" | "opponent";
  playerId: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier: string | null;
  /** Half the width of his projection range: how far he can move the score either way. */
  swing: number;
  /** "±9 either way" for your player, "±9 for Mike" for theirs. */
  label: string;
}

/** The widest-range player still to play on each side (yours first). A player with a range under 1 point is not a swing. */
export function matchupSwingPlayers(inputs: ReadonlyArray<MatchupSwingInput>, opponentName: string): MatchupSwingPlayer[] {
  const best = (side: "mine" | "opponent"): MatchupSwingPlayer | null => {
    let pick: MatchupSwingPlayer | null = null;
    for (const p of inputs) {
      if (p.side !== side || p.done || p.low == null || p.high == null) continue;
      const swing = Math.round(((p.high - p.low) / 2) * 10) / 10;
      if (swing < 1 || (pick && swing <= pick.swing)) continue;
      pick = {
        key: `${side}-${p.playerId ?? p.name}`,
        side,
        playerId: p.playerId,
        name: p.name,
        position: p.position,
        team: p.team,
        tier: p.tier ?? null,
        swing,
        label: side === "mine" ? `±${Math.round(swing)} either way` : `±${Math.round(swing)} for ${opponentName}`,
      };
    }
    return pick;
  };
  return [best("mine"), best("opponent")].filter((p): p is MatchupSwingPlayer => p != null);
}

export interface MatchupCardInput {
  week: number | null;
  /** "Week 7 playoffs" style prefix is the caller's; this builds "WEEK 7 · LIVE". */
  live: boolean;
  final: boolean;
  myName: string;
  opponentName: string;
  /** Real points once games started, else null. */
  myScore: number | null;
  opponentScore: number | null;
  myProjected: number | null;
  opponentProjected: number | null;
  /** 0-100, null when not modeled. */
  winPercent: number | null;
  kickedOff: boolean;
  playersLeft: number | null;
  swing: MatchupSwingPlayer[];
}

export interface MatchupCardModel {
  kicker: string;
  win: { pct: number; label: string; tone: "success" | "danger" | "accent" } | null;
  mine: { name: string; score: string };
  opponent: { name: string; score: string };
  /** Which numbers the big scores are: "points" (live/final) or "projected". */
  basis: "points" | "projected";
  /** 0-100 fill of the win bar; null when not modeled. */
  bar: number | null;
  detail: string | null;
  swing: MatchupSwingPlayer[];
}

export function matchupCardModel(input: MatchupCardInput): MatchupCardModel {
  const state = input.final ? "FINAL" : input.live ? "LIVE" : null;
  const kicker = [input.week != null ? `WEEK ${input.week}` : "THIS WEEK", state].filter(Boolean).join(" · ");
  const wp = input.winPercent != null ? Math.round(input.winPercent) : null;
  const win = wp != null ? { pct: wp, label: `${wp}% win`, tone: (wp >= 55 ? "success" : wp <= 45 ? "danger" : "accent") as "success" | "danger" | "accent" } : null;
  const useReal = input.kickedOff && input.myScore != null && input.opponentScore != null;
  const mineScore = useReal ? fixed(input.myScore) : fixed(input.myProjected);
  const oppScore = useReal ? fixed(input.opponentScore) : fixed(input.opponentProjected);
  const proj = fixed(input.myProjected) && fixed(input.opponentProjected) ? `${useReal && !input.final ? "Proj final" : "Projected"} ${fixed(input.myProjected)} - ${fixed(input.opponentProjected)}` : null;
  const left = input.playersLeft != null && input.playersLeft > 0 && !input.final ? `${input.playersLeft} ${input.playersLeft === 1 ? "player" : "players"} left` : null;
  return {
    kicker,
    win,
    mine: { name: input.myName, score: mineScore ?? "-" },
    opponent: { name: input.opponentName, score: oppScore ?? "-" },
    basis: useReal ? "points" : "projected",
    bar: wp,
    detail: [useReal ? proj : null, left].filter(Boolean).join(" · ") || null,
    swing: input.swing,
  };
}

/** The compact ticker's collapsed line: "WK 7 · You 112.4 - 98.1 Mike · 71%". Used where matchup is one module in a stack. */
export function matchupTickerParts(model: MatchupCardModel, week: number | null): CompactPart[] {
  const tone: CompactTone | undefined = model.win ? (model.win.tone === "success" ? "success" : model.win.tone === "danger" ? "danger" : "accent") : undefined;
  return [
    { key: "wk", text: week != null ? `WK ${week}` : "THIS WEEK", tone: "muted" },
    { key: "score", text: `${model.mine.name} ${model.mine.score} - ${model.opponent.score} ${model.opponent.name}`, strong: true },
    ...(model.win ? [{ key: "win", text: `${model.win.pct}%`, tone }] : []),
  ];
}

/** Fantasy Sim: the Home matchup card from the weekly head-to-head (projection and floor/ceiling only). */
export interface SimMatchupCardInput {
  week: number;
  playoff: boolean;
  opponentName: string;
  youName: string;
  youProjection: number | null;
  oppProjection: number | null;
  /** 0-1 */
  winProb: number | null;
  rows: ReadonlyArray<{
    you: { id: string; headshot_id?: string | null; name: string; pos: string; team: string | null; floor: number; ceiling: number; status?: string } | null;
    opp: { id: string; headshot_id?: string | null; name: string; pos: string; team: string | null; floor: number; ceiling: number; status?: string } | null;
  }>;
}

export function simMatchupCardModel(input: SimMatchupCardInput): MatchupCardModel {
  const swingInputs: MatchupSwingInput[] = [];
  for (const row of input.rows) {
    for (const [side, p] of [["mine", row.you], ["opponent", row.opp]] as const) {
      if (!p) continue;
      swingInputs.push({ playerId: p.headshot_id ?? null, name: p.name, position: p.pos, team: p.team, low: p.floor, high: p.ceiling, done: p.status === "out" || p.status === "bye", side });
    }
  }
  const model = matchupCardModel({
    week: input.week,
    live: false,
    final: false,
    myName: input.youName,
    opponentName: input.opponentName,
    myScore: null,
    opponentScore: null,
    myProjected: input.youProjection,
    opponentProjected: input.oppProjection,
    winPercent: input.winProb != null ? Math.min(99, Math.max(1, Math.round(input.winProb * 100))) : null,
    kickedOff: false,
    playersLeft: null,
    swing: matchupSwingPlayers(swingInputs, input.opponentName),
  });
  return { ...model, kicker: `${input.playoff ? "PLAYOFFS" : "WEEK"} ${input.week}` };
}

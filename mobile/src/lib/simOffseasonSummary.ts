/**
 * The Fantasy Sim offseason page, as data: the three-step stepper (icons, not words-in-chips) and the collapsed summary
 * line of every module (CompactModule `parts`), so the page is a short stack of dense modules with counts instead of flat
 * cards of prose. Pure; byte-identical twin of mobile/src/lib/simOffseasonSummary.ts. First page to apply the "Visual
 * identity" spec in docs/ui-patterns.md.
 */
import { compactCount, type CompactPart } from "./compactModule";
import { simFmtPts, simOrdinal, simPlayoffResultLabel, simReserveUsedLine, type SimGamePlayer, type SimOffseason, type SimOffseasonStage } from "./simGame";

/** The glyph each step and module header uses (web: OffseasonGlyph, app: Ionicons via OFFSEASON_ICON). */
export type OffseasonIcon = "review" | "draft" | "roster" | "season" | "retire" | "aging" | "picks" | "log" | "reserve" | "trade" | "team";

export const OFFSEASON_STEP_ICON: Record<SimOffseasonStage, OffseasonIcon> = { review: "review", rookie_draft: "draft", cutdown: "roster" };

/** One short word under each stepper node (the full name is the aria-label). */
export const OFFSEASON_STEP_SHORT: Record<SimOffseasonStage, string> = { review: "Review", rookie_draft: "Draft", cutdown: "Roster" };

export interface OffseasonStepperItem {
  key: SimOffseasonStage;
  icon: OffseasonIcon;
  short: string;
  /** Full step name for screen readers ("Rookie draft, current step"). */
  aria: string;
  state: "done" | "current" | "todo";
}

export function offseasonStepper(steps: { key: SimOffseasonStage; label: string; state: "done" | "current" | "todo" }[]): OffseasonStepperItem[] {
  return steps.map((s) => ({
    key: s.key,
    icon: OFFSEASON_STEP_ICON[s.key],
    short: OFFSEASON_STEP_SHORT[s.key],
    aria: `${s.label}, ${s.state === "current" ? "current step" : s.state === "done" ? "done" : "to do"}`,
    state: s.state,
  }));
}

type Archive = { record: string; rank: number; playoff_result: string; pf: number };

/** "9-5 · 3rd · Semifinal · 1,240 PF": last season in one line. */
export function offseasonSeasonParts(year: Archive | null, champion: { name: string; is_you: boolean } | null): CompactPart[] {
  if (!year) return [{ key: "n", text: "No season yet", tone: "muted" }];
  return [
    { key: "rec", text: year.record, strong: true },
    { key: "rank", text: simOrdinal(year.rank) },
    { key: "res", text: simPlayoffResultLabel(year.playoff_result), tone: champion?.is_you ? "success" : undefined },
    { key: "pf", text: `${simFmtPts(year.pf)} PF`, tone: "muted" },
  ];
}

export function offseasonRetireParts(retired: { is_yours: boolean }[]): CompactPart[] {
  if (retired.length === 0) return [{ key: "n", text: "Nobody retired", tone: "muted" }];
  const yours = retired.filter((r) => r.is_yours).length;
  return [{ key: "n", text: `${retired.length} retired`, strong: true }, ...(yours ? [{ key: "y", text: `${yours} yours`, tone: "danger" as const, strong: true }] : [])];
}

export function offseasonAgingParts(movers: { delta: number }[]): CompactPart[] {
  if (movers.length === 0) return [{ key: "n", text: "Roster held steady", tone: "muted" }];
  const rose = movers.filter((m) => m.delta >= 0.5).length;
  const fell = movers.filter((m) => m.delta <= -0.5).length;
  return [
    { key: "up", text: `${rose} up`, tone: rose ? "success" : "muted", strong: rose > 0 },
    { key: "down", text: `${fell} down`, tone: fell ? "danger" : "muted", strong: fell > 0 },
  ];
}

export function offseasonPicksParts(mine: { made: unknown | null }[], rounds: number): CompactPart[] {
  if (mine.length === 0) return [{ key: "n", text: "No picks this year", tone: "muted" }];
  const made = mine.filter((m) => m.made).length;
  return [{ key: "n", text: compactCount(mine.length, "pick"), strong: true }, ...(made ? [{ key: "m", text: `${made} made`, tone: "success" as const }] : []), { key: "r", text: `${rounds} rounds`, tone: "muted" }];
}

/** The rookie clock: "R2 P5 · You pick now · 38 left". */
export function offseasonClockParts(d: Pick<SimOffseason["draft"], "on_clock" | "your_turn" | "total" | "pick_index" | "available_count">): CompactPart[] {
  if (!d.on_clock) return [{ key: "n", text: d.pick_index >= d.total && d.total > 0 ? "Draft complete" : "Not started", tone: d.pick_index >= d.total && d.total > 0 ? "success" : "muted", strong: true }];
  const c = d.on_clock;
  return [
    { key: "rp", text: `R${c.round} P${c.n}`, strong: true },
    d.your_turn ? { key: "who", text: "You pick now", tone: "success", strong: true } : { key: "who", text: `${c.team_name ?? "AI team"} picks` },
    { key: "left", text: `${d.available_count} left`, tone: "muted" },
  ];
}

export function offseasonLogParts(made: number, total: number): CompactPart[] {
  return [{ key: "n", text: `${made} of ${total} picks made`, tone: made >= total && total > 0 ? "success" : undefined }];
}

const POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF"];

/** "QB2 RB5 WR6 TE2": the roster's shape in one glance. */
export function offseasonPositionMix(players: ReadonlyArray<Pick<SimGamePlayer, "pos">>): string {
  const counts = new Map<string, number>();
  for (const p of players) counts.set(p.pos, (counts.get(p.pos) ?? 0) + 1);
  return POS_ORDER.filter((pos) => counts.has(pos)).map((pos) => `${pos}${counts.get(pos)}`).join(" ");
}

/** "14/12 · cut 2 · QB2 RB5 WR6 TE2": the roster check summary, the cut count in the danger colour. */
export function offseasonRosterParts(r: { size: number; limit: number; cuts_needed: number }, players: ReadonlyArray<Pick<SimGamePlayer, "pos">>): CompactPart[] {
  const mix = offseasonPositionMix(players);
  return [
    { key: "n", text: `${r.size}/${r.limit} spots`, strong: true, tone: r.cuts_needed > 0 ? "danger" : "success" },
    r.cuts_needed > 0 ? { key: "cut", text: `cut ${r.cuts_needed}`, tone: "danger", strong: true } : { key: "ok", text: "ready", tone: "success" },
    ...(mix ? [{ key: "mix", text: mix, tone: "muted" as const }] : []),
  ];
}

/** "IR 1/2 · Taxi 0/4". */
export function offseasonReserveParts(reserves: Parameters<typeof simReserveUsedLine>[1]): CompactPart[] {
  if (!reserves) return [];
  return [
    ...(reserves.ir_slots > 0 ? [{ key: "ir", text: simReserveUsedLine("ir", reserves).replace(" of ", "/") }] : []),
    ...(reserves.taxi_slots > 0 ? [{ key: "taxi", text: simReserveUsedLine("taxi", reserves).replace(" of ", "/") }] : []),
  ];
}

export function offseasonPickCountParts(n: number): CompactPart[] {
  return [{ key: "n", text: compactCount(n, "pick", undefined, "No picks"), strong: n > 0 }];
}

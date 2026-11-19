// Draft & Watch ("Mock draft, then watch the season"): the sliders, the week-by-week playback lines and the report card the server builds
// (modules/sim/game_watch.py, game_watch_report.py). Pure and import-free: web and the app keep byte-identical copies
// (scripts/check_lib_twins.mjs).

export type SimWatchWaivers = "hands_off" | "balanced" | "aggressive";
export type SimWatchTrades = "off" | "light" | "active";

export interface SimWatchOption<T extends string> {
  value: T;
  label: string;
  note: string;
}

export const SIM_WATCH_WAIVER_OPTIONS: SimWatchOption<SimWatchWaivers>[] = [
  { value: "hands_off", label: "Hands-off", note: "Only fills a starting spot nobody healthy can play." },
  { value: "balanced", label: "Balanced", note: "Fills holes and makes one add a week when it clearly helps your lineup." },
  { value: "aggressive", label: "Aggressive", note: "Chases upgrades: up to two adds a week at a lower bar." },
];

export const SIM_WATCH_TRADE_OPTIONS: SimWatchOption<SimWatchTrades>[] = [
  { value: "off", label: "Off", note: "No trades. Offers are ignored." },
  { value: "light", label: "Light", note: "Accepts a clearly good offer, at most one every four weeks." },
  { value: "active", label: "Active", note: "Accepts good offers more often, up to one a week." },
];

/** The approved defaults. */
export const SIM_WATCH_DEFAULTS: { waivers: SimWatchWaivers; trades: SimWatchTrades } = { waivers: "balanced", trades: "light" };

export interface SimWatchSettingsLike {
  watch_v?: number;
  watch_waivers?: string;
  watch_trades?: string;
  teams?: number;
  scoring?: string;
  user_slot?: number;
  difficulty?: string;
  te_premium?: number;
  superflex?: boolean;
  include_k?: boolean;
  include_def?: boolean;
  bench?: number;
  flex_type?: string;
}

/** The game's Draft & Watch sliders, or null for an ordinary game. */
export function simWatchSliders(settings: SimWatchSettingsLike | null | undefined): { waivers: SimWatchWaivers; trades: SimWatchTrades } | null {
  if (!settings || !settings.watch_v) return null;
  const waivers = SIM_WATCH_WAIVER_OPTIONS.find((o) => o.value === settings.watch_waivers)?.value ?? SIM_WATCH_DEFAULTS.waivers;
  const trades = SIM_WATCH_TRADE_OPTIONS.find((o) => o.value === settings.watch_trades)?.value ?? SIM_WATCH_DEFAULTS.trades;
  return { waivers, trades };
}

export function simWatchWaiverLabel(value: string): string {
  return SIM_WATCH_WAIVER_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export function simWatchTradeLabel(value: string): string {
  return SIM_WATCH_TRADE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

/** The create body for "Run it back" (same league, same draft slot) or "Draft again" (same league, a fresh random slot). */
export function simWatchRerunBody(settings: SimWatchSettingsLike, sameSlot: boolean): Record<string, unknown> {
  const sliders = simWatchSliders(settings) ?? { waivers: SIM_WATCH_DEFAULTS.waivers, trades: SIM_WATCH_DEFAULTS.trades };
  return {
    watch: true,
    watch_waivers: sliders.waivers,
    watch_trades: sliders.trades,
    ...(settings.teams ? { teams: settings.teams } : {}),
    ...(settings.scoring ? { scoring: settings.scoring } : {}),
    ...(settings.difficulty ? { difficulty: settings.difficulty } : {}),
    ...(typeof settings.te_premium === "number" ? { te_premium: settings.te_premium } : {}),
    ...(typeof settings.superflex === "boolean" ? { superflex: settings.superflex } : {}),
    ...(typeof settings.include_k === "boolean" ? { include_k: settings.include_k } : {}),
    ...(typeof settings.include_def === "boolean" ? { include_def: settings.include_def } : {}),
    ...(typeof settings.bench === "number" ? { bench: settings.bench } : {}),
    ...(settings.flex_type && settings.flex_type !== "flex" ? { flex_type: settings.flex_type } : {}),
    random_team_name: true,
    user_slot: sameSlot && settings.user_slot ? settings.user_slot : null,
  };
}

interface RecapLike {
  week?: number;
  kind?: string;
  your_game?: { result?: string; your_pts?: number; opp_pts?: number; opponent_name?: string } | null;
  standings?: { is_you?: boolean; rank?: number }[] | null;
}

function ordinal(n: number): string {
  const v = n % 100;
  const suffix = v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/** One playback row: "Wk 3 · W 112.4-98.1 vs Harbor Hawks · 2nd". A week with no game (a playoff bye) says so. */
export interface SimWatchLine {
  week: number;
  text: string;
  result: "W" | "L" | "T" | "";
  /** "Wk 3 vs Harbor Hawks" and "112.4 - 98.1" for the results list. */
  label: string;
  score: string;
}

export function simWatchPlaybackLine(recap: RecapLike | null | undefined): SimWatchLine | null {
  if (!recap || typeof recap.week !== "number") return null;
  const g = recap.your_game;
  const rank = recap.standings?.find((row) => row.is_you)?.rank;
  const rankText = rank ? ` · ${ordinal(rank)}` : "";
  const label = recap.kind === "playoff" ? "Playoffs" : `Wk ${recap.week}`;
  if (!g || typeof g.your_pts !== "number") return { week: recap.week, text: `${label} · bye${rankText}`, result: "", label: `${label} · bye`, score: "" };
  const result = g.result === "win" ? "W" : g.result === "loss" ? "L" : "T";
  const opp = typeof g.opp_pts === "number" ? `-${g.opp_pts.toFixed(1)}` : "";
  const score = `${g.your_pts.toFixed(1)}${typeof g.opp_pts === "number" ? ` - ${g.opp_pts.toFixed(1)}` : ""}`;
  return {
    week: recap.week,
    text: `${label} · ${result} ${g.your_pts.toFixed(1)}${opp}${g.opponent_name ? ` vs ${g.opponent_name}` : ""}${rankText}`,
    result,
    label: `${label}${g.opponent_name ? ` vs ${g.opponent_name}` : ""}`,
    score,
  };
}

/** "Jalen Pruitt" -> "J. Pruitt". */
export function simWatchShortName(name: string | null | undefined): string {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return parts[0] ?? "";
  const suffix = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i;
  const last = suffix.test(parts[parts.length - 1]) && parts.length > 2 ? `${parts[parts.length - 2]} ${parts[parts.length - 1]}` : parts[parts.length - 1];
  return `${parts[0][0].toUpperCase()}. ${last}`;
}

interface WaiverRecapLike {
  waivers?: { team_id?: string; ok?: boolean; add?: { name?: string } | null; drop?: { name?: string } | null }[] | null;
}

/** The moves made for the user in a played week (waiver adds that went through): "Added R. Duke", "dropped M. Hale". */
export function simWatchMoves(recap: WaiverRecapLike | null | undefined, youTeamId: string | null | undefined): { title: string; sub: string }[] {
  if (!recap?.waivers || !youTeamId) return [];
  return recap.waivers
    .filter((w) => w.team_id === youTeamId && w.ok && w.add?.name)
    .map((w) => ({ title: `Added ${simWatchShortName(w.add?.name)}`, sub: w.drop?.name ? `Dropped ${simWatchShortName(w.drop.name)}` : "Used an open roster spot" }));
}

export interface SimWatchPlayer {
  id: string;
  headshot_id: string | null;
  name: string;
  pos: string;
  team: string;
}

export interface SimWatchWhatIf {
  id: string;
  title: string;
  delta: number;
  text: string;
  players: SimWatchPlayer[];
}

export interface SimWatchReport {
  sliders: { waivers: string; trades: string };
  standing: { rank: number; teams: number; record: string; outcome: string; champion: string | null };
  draft: { then: { grade: string; rank: number | null } | null; now: { grade: string; rank: number; points: number }; teams: number };
  best_value: { player: SimWatchPlayer | null; pick: string; pts: number; over_round: number } | null;
  bust: { player: SimWatchPlayer | null; pick: string; projected: number; actual: number; gap: number; why: string; why_tag: string | null; games_missed: number } | null;
  moves: { waivers: number; trades: number };
  what_ifs: SimWatchWhatIf[];
  /** The report as Wrapped-style cards (lib/wrapped.ts normalizeWrappedDeck reads them). */
  cards: unknown[];
}

function rec(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function player(value: unknown): SimWatchPlayer | null {
  const p = rec(value);
  if (typeof p.id !== "string" || typeof p.name !== "string") return null;
  return { id: p.id, headshot_id: typeof p.headshot_id === "string" ? p.headshot_id : null, name: p.name, pos: typeof p.pos === "string" ? p.pos : "", team: typeof p.team === "string" ? p.team : "" };
}

function num(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/** Defensive parse of the /watch-report body's report; null when it is missing or malformed. */
export function normalizeWatchReport(raw: unknown): SimWatchReport | null {
  const r = rec(raw);
  const standing = rec(r.standing);
  const draft = rec(r.draft);
  const now = rec(draft.now);
  if (typeof standing.rank !== "number" || typeof now.grade !== "string") return null;
  const then = rec(draft.then);
  const best = rec(r.best_value);
  const bust = rec(r.bust);
  const moves = rec(r.moves);
  const sliders = rec(r.sliders);
  return {
    sliders: { waivers: String(sliders.waivers ?? ""), trades: String(sliders.trades ?? "") },
    standing: { rank: standing.rank, teams: num(standing.teams), record: String(standing.record ?? ""), outcome: String(standing.outcome ?? ""), champion: typeof standing.champion === "string" ? standing.champion : null },
    draft: {
      then: typeof then.grade === "string" ? { grade: then.grade, rank: typeof then.rank === "number" ? then.rank : null } : null,
      now: { grade: now.grade, rank: num(now.rank), points: num(now.points) },
      teams: num(draft.teams),
    },
    best_value: Object.keys(best).length ? { player: player(best.player), pick: String(best.pick ?? ""), pts: num(best.pts), over_round: num(best.over_round) } : null,
    bust: Object.keys(bust).length
      ? { player: player(bust.player), pick: String(bust.pick ?? ""), projected: num(bust.projected), actual: num(bust.actual), gap: num(bust.gap), why: String(bust.why ?? ""), why_tag: typeof bust.why_tag === "string" ? bust.why_tag : null, games_missed: num(bust.games_missed) }
      : null,
    moves: { waivers: num(moves.waivers), trades: num(moves.trades) },
    cards: Array.isArray(r.cards) ? r.cards : [],
    what_ifs: (Array.isArray(r.what_ifs) ? r.what_ifs : []).map((w) => {
      const x = rec(w);
      return { id: String(x.id ?? ""), title: String(x.title ?? ""), delta: num(x.delta), text: String(x.text ?? ""), players: (Array.isArray(x.players) ? x.players : []).map(player).filter((p): p is SimWatchPlayer => p !== null) };
    }),
  };
}

const GRADE_ORDER = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A"];

/** How the draft's grade moved once the season was played: up, same or down. */
export function simWatchGradeMove(then: string | null | undefined, now: string): "up" | "same" | "down" {
  if (!then) return "same";
  const a = GRADE_ORDER.indexOf(then);
  const b = GRADE_ORDER.indexOf(now);
  if (a < 0 || b < 0 || a === b) return "same";
  return b > a ? "up" : "down";
}

export function simWatchOutcomeText(outcome: string): string {
  switch (outcome) {
    case "champion": return "Champions";
    case "runner_up": return "Lost in the final";
    case "semifinal": return "Lost in the semifinal";
    case "missed": return "Missed the playoffs";
    default: return outcome.startsWith("lost_round") ? "Lost in the playoffs" : "Season complete";
  }
}

/** The report card's plain-text share summary (no player full names: short names only). */
export function simWatchReportText(report: SimWatchReport, short: (name: string) => string): string {
  const lines = [
    `Draft & Watch: ${report.standing.record}, ${ordinal(report.standing.rank)} of ${report.standing.teams}. ${simWatchOutcomeText(report.standing.outcome)}.`,
    `Draft grade: ${report.draft.then ? `${report.draft.then.grade} then, ` : ""}${report.draft.now.grade} now.`,
  ];
  if (report.best_value?.player) lines.push(`Best pick: ${short(report.best_value.player.name)} (+${report.best_value.over_round.toFixed(1)} over his round).`);
  if (report.bust?.player) lines.push(`Biggest bust: ${short(report.bust.player.name)}. ${report.bust.why}.`);
  return [...lines, "", "Mock draft, then watch the season on FantasyDesk."].join("\n");
}

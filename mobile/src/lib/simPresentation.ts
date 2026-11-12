/**
 * Season outlook simulation presentation: the pure copy and shaping both the web page and
 * the app screen render from. Web and mobile hold a byte-identical copy of
 * this file (scripts/check_lib_twins.mjs), so it has no imports.
 *
 * The sim is a what-if: nothing here reads or writes real league data, and
 * every screen says so. The backend contract is docs/fantasy-sim-api.md.
 */

export type SimPosture = "win_now" | "balanced" | "rebuild";
export type SimMode = "remaining" | "full";

export interface SimStrategy {
  posture: SimPosture;
  trade_aggressiveness: number;
  waiver_aggressiveness: number;
  lineup_auto_set: boolean;
  protected_player_ids: string[];
}

export interface SimUpsell {
  title: string;
  body: string;
}

/** Fields every /v1/sim/* success or not-ready body carries. */
export interface SimEnvelope {
  ok: boolean;
  reason?: string;
  is_premium?: boolean;
  upsell?: SimUpsell | null;
  error?: string;
}

export interface SimPersonaOption {
  id: string;
  label: string;
  blurb: string;
}

export interface SimStatusResponse extends SimEnvelope {
  enabled?: boolean;
  engine_version?: string;
  modes?: SimMode[];
  max_worlds?: number;
  personas?: SimPersonaOption[];
}

export interface SimWorld {
  id: string;
  source_league_id: string;
  league_name: string;
  mode: SimMode;
  seed: number;
  engine_version: string;
  status: string;
  strategy: SimStrategy;
  grade_letter: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimWorldResponse extends SimEnvelope {
  world?: SimWorld;
  team?: { team_id: string; name: string };
  notes?: string[];
}

export interface SimWorldsResponse extends SimEnvelope {
  worlds: SimWorld[];
  max_worlds?: number;
}

export interface SimAsset {
  player_id?: string;
  name?: string;
  pos?: string;
  label?: string;
  /** "pick" for a draft pick (no position). */
  kind?: string;
}

export interface SimStandingRow {
  team_id: string;
  name: string;
  owner?: string;
  is_user: boolean;
  persona_id?: string;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  seed?: number;
  made_playoffs: boolean;
  playoff_result: string;
}

export interface SimPlayoffGame {
  home: string;
  away: string;
  home_pts: number;
  away_pts: number;
  winner?: string;
}

export interface SimPlayoffRound {
  round: number;
  week: number;
  games: SimPlayoffGame[];
}

export interface SimEvent {
  week: number;
  seq: number;
  type: "trade" | "waiver" | "drop" | string;
  team?: string;
  partner?: string;
  involves_user: boolean;
  add?: SimAsset | null;
  drop?: SimAsset | null;
  player?: SimAsset | null;
  gives?: SimAsset[];
  gets?: SimAsset[];
  gain?: number;
}

export interface SimPersonaReport {
  team_id: string;
  name: string;
  is_user: boolean;
  persona_id: string;
  label?: string;
  blurb?: string;
  power_percentile?: number;
  avg_age?: number;
}

export interface SimGradeComponent {
  key: string;
  label: string;
  score: number;
  weight: number;
}

export interface SimGrade {
  letter: string;
  score: number;
  grade_points: number;
  components: SimGradeComponent[];
  summary: {
    record?: string;
    finish?: number;
    points_rank?: number;
    playoff_result?: string;
    lineup_efficiency?: number;
    luck_wins?: number;
  };
}

export interface SimDecision {
  kind: string;
  week?: number;
  title: string;
  detail: string;
  impact?: {
    season_value?: number;
    wins?: number;
    points_per_game?: number;
    playoff_result_with?: string;
    playoff_result_without?: string;
  };
}

export interface SimUserLine {
  team_id: string;
  wins: number;
  losses: number;
  ties: number;
  pf: number;
  pa: number;
  seed?: number;
  playoff_result: string;
  made_playoffs: boolean;
  lineup_efficiency?: number;
  expected_wins?: number;
  games?: number;
}

export interface SimResult {
  engine_version: string;
  seed: number;
  mode: SimMode;
  start_week?: number;
  strategy: SimStrategy;
  standings: SimStandingRow[];
  playoffs: SimPlayoffRound[];
  champion?: string;
  events: SimEvent[];
  personas: SimPersonaReport[];
  user: SimUserLine;
  grade: SimGrade;
  decisions_that_mattered: SimDecision[];
}

export interface SimRunResponse extends SimEnvelope {
  world?: SimWorld;
  result?: SimResult | null;
}

export const SIM_LABEL = "Simulation";
export const SIM_DISCLAIMER = "This is a simulation. Nothing here happens in your real league.";

export const DEFAULT_SIM_STRATEGY: SimStrategy = {
  posture: "balanced",
  trade_aggressiveness: 0.5,
  waiver_aggressiveness: 0.5,
  lineup_auto_set: true,
  protected_player_ids: [],
};

export const SIM_POSTURE_OPTIONS: readonly { value: SimPosture; label: string; blurb: string }[] = [
  { value: "win_now", label: "Win now", blurb: "Values players who help this season most." },
  { value: "balanced", label: "Balanced", blurb: "Weighs this season and the future evenly." },
  { value: "rebuild", label: "Rebuild", blurb: "Values youth and the future over this season." },
];

export const SIM_MODE_OPTIONS: readonly { value: SimMode; label: string; blurb: string }[] = [
  { value: "remaining", label: "Rest of this season", blurb: "Keeps your real record and plays the weeks still to come." },
  { value: "full", label: "Whole season", blurb: "Replays every week from the start on today's rosters." },
];

/** Plain-language level for a 0..1 slider. */
export function simLevelLabel(value: number): string {
  if (value <= 0.05) return "Off";
  if (value < 0.34) return "Low";
  if (value < 0.67) return "Medium";
  if (value < 0.95) return "High";
  return "Max";
}

export function simPostureLabel(posture: string): string {
  return SIM_POSTURE_OPTIONS.find((option) => option.value === posture)?.label ?? "Balanced";
}

/** One line that says what the strategy is, for the result header and A/B. */
export function simStrategySummary(strategy: SimStrategy): string {
  const parts = [
    simPostureLabel(strategy.posture),
    `trades ${simLevelLabel(strategy.trade_aggressiveness).toLowerCase()}`,
    `waivers ${simLevelLabel(strategy.waiver_aggressiveness).toLowerCase()}`,
    strategy.lineup_auto_set ? "auto lineup" : "set-and-forget lineup",
  ];
  if (strategy.protected_player_ids.length > 0) {
    parts.push(`${strategy.protected_player_ids.length} protected`);
  }
  return parts.join(", ");
}

export function simStrategyEqual(a: SimStrategy, b: SimStrategy): boolean {
  return (
    a.posture === b.posture &&
    a.trade_aggressiveness === b.trade_aggressiveness &&
    a.waiver_aggressiveness === b.waiver_aggressiveness &&
    a.lineup_auto_set === b.lineup_auto_set &&
    [...a.protected_player_ids].sort().join(",") === [...b.protected_player_ids].sort().join(",")
  );
}

export type SimGate =
  | { kind: "ready" }
  | { kind: "premium"; upsell: SimUpsell | null }
  | { kind: "unavailable"; cause: SimUnavailableCause };

/** Why the sim cannot open: its routes 404 ("off": SIM_ENABLED unset, or the
 * API not restarted since it was set) or its storage answered
 * sim_storage_unavailable ("storage": docs/supabase_sim.sql not applied, or
 * Supabase unreachable). */
export type SimUnavailableCause = "off" | "storage";

/** What a /v1/sim response means for the page: show it, upsell, or hide. */
export function simGate(body: (SimEnvelope & { enabled?: boolean }) | null | undefined): SimGate {
  if (!body) return { kind: "unavailable", cause: "off" };
  if (body.reason === "premium_required" || body.is_premium === false) {
    return { kind: "premium", upsell: body.upsell ?? null };
  }
  if (body.reason === "sim_storage_unavailable") return { kind: "unavailable", cause: "storage" };
  if (body.enabled === false) return { kind: "unavailable", cause: "off" };
  return { kind: "ready" };
}

/** Customer-safe copy for each unavailable cause, so "not switched on" and
 * "temporarily unavailable" are never the same screen. */
export function simUnavailableCopy(cause: SimUnavailableCause): { title: string; subtitle: string } {
  if (cause === "storage") {
    return {
      title: "Season outlook is temporarily unavailable",
      subtitle: "It is switched on, but we cannot save simulations right now. Try again in a little while.",
    };
  }
  return {
    title: "Season outlook is coming soon",
    subtitle: "Pick a strategy, play out the season, and see how you would grade. It is not switched on yet. Check back soon.",
  };
}

/** True when the sim is simply not switched on: its routes 404 until then. */
export function isSimOffError(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { status?: number }).status === 404;
}

const REASON_COPY: Record<string, string> = {
  league_unavailable: "We could not read this league from Sleeper right now. Try again in a moment.",
  team_not_found: "We could not find your team in this league. Pick the team to play as.",
  season_complete: "This league's regular season is over, so there is nothing left to play. Choose Whole season instead.",
  players_unavailable: "Player values are not available right now. Try again soon.",
  invalid_mode: "That simulation length is not supported.",
  world_limit_reached: "You have reached the limit of saved simulations. Delete one to start another.",
  not_simulated: "This simulation has not been played yet.",
  sim_storage_unavailable: "Season outlook is not available yet.",
};

/** Customer-safe copy for a `reason` code; empty for success. */
export function simReasonMessage(reason: string | undefined): string {
  if (!reason) return "";
  return REASON_COPY[reason] ?? "Something went wrong running the simulation. Try again.";
}

const NOTE_COPY: Record<string, string> = {
  bye_weeks_not_modeled: "Bye weeks are not modeled.",
  bye_weeks_unavailable: "Bye weeks could not be loaded, so no player is on bye.",
  draft_picks_unavailable: "Draft picks are not part of trades in this simulation.",
  def_idp_slots_not_modeled: "Defense and IDP lineup slots are not modeled.",
  offseason_full_season: "It is the offseason, so the whole season is simulated.",
  playoff_reseed_not_modeled: "Playoff re-seeding between rounds is not modeled.",
};

/** Plain-language caveats from the world's `notes`. */
export function simNoteMessages(notes: readonly string[] | undefined): string[] {
  const out: string[] = [];
  for (const note of notes ?? []) {
    const [key, arg] = note.split(":");
    if (NOTE_COPY[key]) out.push(NOTE_COPY[key]);
    else if (key === "schedule_estimated_weeks") out.push(`The schedule for ${arg && arg.includes(",") ? "weeks" : "week"} ${arg ?? ""} is estimated.`);
    else if (key === "projection_fallback_players") out.push(`${arg ?? "Some"} players use estimated scoring.`);
    else if (key === "playoff_format_approximated") out.push("The playoff format is approximated.");
  }
  return out;
}

const PLAYOFF_RESULT_LABEL: Record<string, string> = {
  missed: "Missed the playoffs",
  lost_round_1: "Lost in round 1",
  lost_round_2: "Lost in round 2",
  semifinal: "Lost in the semifinal",
  runner_up: "Runner-up",
  champion: "Champion",
};

export function simPlayoffResultLabel(result: string | undefined): string {
  if (!result) return "";
  return PLAYOFF_RESULT_LABEL[result] ?? result.replace(/_/g, " ");
}

/** Higher is deeper: for comparing two runs. */
export function simPlayoffDepth(result: string | undefined): number {
  switch (result) {
    case "champion":
      return 5;
    case "runner_up":
      return 4;
    case "semifinal":
      return 3;
    case "lost_round_2":
      return 2;
    case "lost_round_1":
      return 1;
    default:
      return 0;
  }
}

export type SimTone = "success" | "accent" | "warning" | "danger";

/** Grade colour: a typical manager is a C, so C is the neutral-warning band. */
export function simGradeTone(letter: string | undefined): SimTone {
  const first = (letter ?? "").trim().charAt(0).toUpperCase();
  if (first === "A") return "success";
  if (first === "B") return "accent";
  if (first === "C") return "warning";
  return "danger";
}

export function simFormatRecord(line: { wins: number; losses: number; ties: number }): string {
  return line.ties > 0 ? `${line.wins}-${line.losses}-${line.ties}` : `${line.wins}-${line.losses}`;
}

export function simFormatPoints(value: number | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "-";
}

export function simFormatPercent(value: number | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value * 100)}%` : "-";
}

/** Signed, one decimal ("+1.5", "-0.4", "0.0"). */
export function simFormatSigned(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "0.0";
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}

export function simTeamNames(result: Pick<SimResult, "standings">): Record<string, string> {
  const names: Record<string, string> = {};
  for (const row of result.standings) names[row.team_id] = row.is_user ? `${row.name} (you)` : row.name;
  return names;
}

function assetLabel(asset: SimAsset | null | undefined): string {
  if (!asset) return "a player";
  const base = asset.name || asset.label || "a pick";
  return asset.pos ? `${base} (${asset.pos})` : base;
}

function assetList(assets: SimAsset[] | undefined): string {
  const labels = (assets ?? []).map(assetLabel);
  return labels.length > 0 ? labels.join(" + ") : "nothing";
}

export interface SimTimelineItem {
  key: string;
  week: number;
  kind: "trade" | "waiver" | "drop";
  title: string;
  detail: string;
  involvesUser: boolean;
}

/** Transaction log as readable rows, in the order they happened. */
export function simTimeline(
  events: readonly SimEvent[],
  names: Record<string, string>,
  options: { onlyUser?: boolean } = {},
): SimTimelineItem[] {
  const items: SimTimelineItem[] = [];
  const sorted = [...events].sort((a, b) => a.week - b.week || a.seq - b.seq);
  for (const event of sorted) {
    if (options.onlyUser && !event.involves_user) continue;
    const team = names[event.team ?? ""] ?? "A team";
    const key = `${event.week}-${event.seq}`;
    if (event.type === "trade") {
      const partner = names[event.partner ?? ""] ?? "another team";
      items.push({
        key,
        week: event.week,
        kind: "trade",
        title: `${team} traded with ${partner}`,
        detail: `Sent ${assetList(event.gives)}, got ${assetList(event.gets)}.`,
        involvesUser: event.involves_user,
      });
    } else if (event.type === "waiver") {
      items.push({
        key,
        week: event.week,
        kind: "waiver",
        title: `${team} picked up ${assetLabel(event.add)}`,
        detail: event.drop ? `Dropped ${assetLabel(event.drop)}.` : "No one dropped.",
        involvesUser: event.involves_user,
      });
    } else if (event.type === "drop") {
      items.push({
        key,
        week: event.week,
        kind: "drop",
        title: `${team} dropped ${assetLabel(event.player)}`,
        detail: "Released to the waiver wire.",
        involvesUser: event.involves_user,
      });
    }
  }
  return items;
}

/** Playoff round name counted back from the final. */
export function simRoundLabel(index: number, total: number): string {
  const fromEnd = total - 1 - index;
  if (fromEnd === 0) return "Championship";
  if (fromEnd === 1) return "Semifinals";
  if (fromEnd === 2) return "Quarterfinals";
  return `Round ${index + 1}`;
}

export function simDecisionKindLabel(kind: string): string {
  switch (kind) {
    case "trade":
      return "Trade";
    case "waiver":
      return "Waiver pickup";
    case "strategy_trades":
      return "Trade approach";
    case "strategy_waivers":
      return "Waiver approach";
    case "strategy_lineup":
      return "Lineup approach";
    default:
      return "Decision";
  }
}

export interface SimCompareRow {
  key: string;
  label: string;
  before: string;
  after: string;
  /** Change in the user's favour (1), against (-1) or none (0). */
  direction: -1 | 0 | 1;
}

function direction(delta: number): -1 | 0 | 1 {
  if (Math.abs(delta) < 1e-9) return 0;
  return delta > 0 ? 1 : -1;
}

/** Side-by-side of two runs of the same world (same dice, new strategy). */
export function simCompareRows(before: SimResult, after: SimResult): SimCompareRow[] {
  const b = before.user;
  const a = after.user;
  const moves = (r: SimResult) => String(r.events.filter((e) => e.involves_user && e.type !== "drop").length);
  return [
    { key: "grade", label: "Grade", before: before.grade.letter, after: after.grade.letter, direction: direction(after.grade.grade_points - before.grade.grade_points) },
    { key: "record", label: "Record", before: simFormatRecord(b), after: simFormatRecord(a), direction: direction(a.wins - b.wins) },
    {
      key: "playoffs",
      label: "Playoffs",
      before: simPlayoffResultLabel(b.playoff_result),
      after: simPlayoffResultLabel(a.playoff_result),
      direction: direction(simPlayoffDepth(a.playoff_result) - simPlayoffDepth(b.playoff_result)),
    },
    { key: "pf", label: "Points for", before: simFormatPoints(b.pf), after: simFormatPoints(a.pf), direction: direction(a.pf - b.pf) },
    { key: "moves", label: "Your trades and pickups", before: moves(before), after: moves(after), direction: 0 },
  ];
}

/** One sentence on what changing the strategy did. */
export function simCompareHeadline(before: SimResult, after: SimResult): string {
  const winsDelta = after.user.wins - before.user.wins;
  const depth = simPlayoffDepth(after.user.playoff_result) - simPlayoffDepth(before.user.playoff_result);
  if (winsDelta === 0 && depth === 0 && after.grade.letter === before.grade.letter) {
    return "The new strategy finished the same as the last one.";
  }
  const wins = winsDelta === 0 ? "the same wins" : `${Math.abs(winsDelta)} ${Math.abs(winsDelta) === 1 ? "win" : "wins"} ${winsDelta > 0 ? "more" : "fewer"}`;
  const playoffs = depth === 0 ? "" : depth > 0 ? ", and a deeper playoff run" : ", and an earlier playoff exit";
  return `The new strategy got ${wins}${playoffs}. Same dice, so the difference is your strategy.`;
}

/** Where a team's strength sits in the league, as plain text. */
export function simPowerLabel(percentile: number | undefined): string {
  if (typeof percentile !== "number") return "";
  if (percentile >= 0.75) return "Top of the league";
  if (percentile >= 0.5) return "Above average";
  if (percentile >= 0.25) return "Below average";
  return "Bottom of the league";
}

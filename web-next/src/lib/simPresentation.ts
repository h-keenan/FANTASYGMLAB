/**
 * Season Outlook presentation: the pure copy and shaping both the web page and
 * the app screen render from. Web and mobile hold a byte-identical copy of
 * this file (scripts/check_lib_twins.mjs), so it has no imports.
 *
 * Season Outlook is a one-tap forecast of the user's real league: no
 * strategy, no setup. Nothing here reads or writes real league data, and
 * every screen says what the numbers are (as of today, on current rosters,
 * rest of season). The backend contract is GET /v1/sim/forecast in
 * docs/fantasy-sim-api.md.
 */

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

export type SimFactorKind = "game" | "waiver" | "trade";

export interface SimSwingFactor {
  kind: SimFactorKind;
  week?: number | null;
  title: string;
  detail: string;
  /** Change in playoff odds, 0..1 (a game: win minus lose). */
  playoff_delta: number;
  /** Change in title odds, 0..1. */
  title_delta: number;
  players?: string[];
}

export interface SimFinishBucket {
  finish: number;
  probability: number;
}

export interface SimForecast {
  samples: number;
  start_week: number;
  regular_season_end: number;
  weeks_remaining: number;
  team: { team_id: string; name: string };
  current: { wins: number; losses: number; ties: number };
  odds: { playoffs: number; finals: number; title: number; playoff_spots: number };
  record: { wins: number; losses: number; wins_low: number; wins_high: number; projected: string; games: number };
  finish: { median: number; low: number; high: number; teams: number; distribution: SimFinishBucket[] };
  swing_factors: SimSwingFactor[];
}

export interface SimForecastResponse extends SimEnvelope {
  forecast?: SimForecast;
  notes?: string[];
  mode?: "remaining" | "full";
  as_of?: string;
}

export const SIM_LABEL = "Forecast";
export const SIM_DISCLAIMER = "A forecast from simulated seasons, not a promise. Nothing here changes your real league.";
export const SIM_GAME_CARD = {
  title: "Want to make the calls yourself?",
  body: "Play Fantasy Sim: run a team week by week, set lineups, work waivers and make trades.",
  action: "Play Fantasy Sim",
} as const;

export type SimGate =
  | { kind: "ready" }
  | { kind: "premium"; upsell: SimUpsell | null }
  | { kind: "unavailable"; cause: SimUnavailableCause };

/** Why the forecast cannot open: its routes 404 ("off": SIM_ENABLED unset, or
 * the API not restarted since it was set). */
export type SimUnavailableCause = "off";

/** What a /v1/sim response means for the page: show it, upsell, or hide. */
export function simGate(body: (SimEnvelope & { enabled?: boolean }) | null | undefined): SimGate {
  if (!body) return { kind: "unavailable", cause: "off" };
  if (body.reason === "premium_required" || body.is_premium === false) {
    return { kind: "premium", upsell: body.upsell ?? null };
  }
  if (body.enabled === false) return { kind: "unavailable", cause: "off" };
  return { kind: "ready" };
}

/** Customer-safe copy for the unavailable state. */
export function simUnavailableCopy(): { title: string; subtitle: string } {
  return {
    title: "Season Outlook is coming soon",
    subtitle: "One tap will show your playoff odds, projected finish and title odds. It is not switched on yet. Check back soon.",
  };
}

/** True when the forecast is simply not switched on: its routes 404 until then. */
export function isSimOffError(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { status?: number }).status === 404;
}

const REASON_COPY: Record<string, string> = {
  league_unavailable: "We could not read this league from Sleeper right now. Try again in a moment.",
  team_not_found: "We could not find your team in this league.",
  season_complete: "This league's regular season is over, so there is no rest-of-season forecast left to make.",
  players_unavailable: "Player values are not available right now. Try again soon.",
};

/** Customer-safe copy for a `reason` code; empty for success. */
export function simReasonMessage(reason: string | undefined): string {
  if (!reason) return "";
  return REASON_COPY[reason] ?? "We could not build your forecast. Try again.";
}

const NOTE_COPY: Record<string, string> = {
  bye_weeks_unavailable: "Bye weeks could not be loaded, so no player is on bye.",
  def_idp_slots_not_modeled: "Defense and IDP lineup slots are not modeled.",
  offseason_full_season: "It is the offseason, so the forecast covers a whole season on today's rosters.",
  playoff_reseed_not_modeled: "Playoff re-seeding between rounds is not modeled.",
};

/** Plain-language caveats from the forecast's `notes`. */
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

export type SimTone = "success" | "accent" | "warning" | "danger";

/** Odds colour: how comfortable the position is. */
export function simOddsTone(probability: number | undefined): SimTone {
  const p = typeof probability === "number" ? probability : 0;
  if (p >= 0.6) return "success";
  if (p >= 0.35) return "accent";
  if (p >= 0.15) return "warning";
  return "danger";
}

/** Whole-percent odds, never a false 0% or 100%. */
export function simFormatPercent(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  const pct = value * 100;
  if (pct > 0 && pct < 1) return "<1%";
  if (pct > 99 && pct < 100) return ">99%";
  return `${Math.round(pct)}%`;
}

/** Signed percentage points ("+15 pts", "-4 pts"). */
export function simFormatPointsSwing(delta: number): string {
  const pts = Math.round(delta * 100);
  return `${pts > 0 ? "+" : ""}${pts} pts`;
}

export function simOrdinal(n: number): string {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** "4th" or "3rd to 6th". */
export function simFinishRange(finish: SimForecast["finish"]): string {
  return finish.low === finish.high ? simOrdinal(finish.median) : `${simOrdinal(finish.low)} to ${simOrdinal(finish.high)}`;
}

/** "8 to 11 wins" or "9 wins". */
export function simWinsRange(record: SimForecast["record"]): string {
  const low = Math.round(record.wins_low);
  const high = Math.round(record.wins_high);
  return low === high ? `${low} ${low === 1 ? "win" : "wins"}` : `${low} to ${high} wins`;
}

export function simFormatCurrent(current: SimForecast["current"]): string {
  return current.ties > 0 ? `${current.wins}-${current.losses}-${current.ties}` : `${current.wins}-${current.losses}`;
}

/** One sentence verdict on the playoff picture. */
export function simHeadline(forecast: SimForecast): string {
  const p = forecast.odds.playoffs;
  const pct = simFormatPercent(p);
  if (p >= 0.9) return `You are a near lock for the playoffs (${pct}).`;
  if (p >= 0.6) return `You are in good shape: you make the playoffs in ${pct} of simulated seasons.`;
  if (p >= 0.35) return `It is a coin flip: you make the playoffs in ${pct} of simulated seasons.`;
  if (p >= 0.1) return `You are on the outside looking in: ${pct} playoff odds.`;
  return `The playoffs are a long shot: ${pct} odds.`;
}

/** The scope line every screen shows: what these numbers are. */
export function simScopeLine(forecast: SimForecast, mode?: "remaining" | "full", asOf?: string): string {
  const when = asOf ? simAsOfDate(asOf) : "today";
  if (mode === "full") return `As of ${when}, on current rosters, a whole season (it is the offseason).`;
  const left = forecast.weeks_remaining;
  return `As of ${when}, on current rosters, rest of season (${left} ${left === 1 ? "game" : "games"} left).`;
}

function simAsOfDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "today";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function simFactorKindLabel(kind: string): string {
  switch (kind) {
    case "game":
      return "Key game";
    case "waiver":
      return "Waiver wire";
    case "trade":
      return "Trade";
    default:
      return "Swing factor";
  }
}

/** What a factor is worth, in plain words. */
export function simFactorImpact(factor: SimSwingFactor): string {
  const playoff = `${simFormatPointsSwing(factor.playoff_delta)} playoff odds`;
  if (Math.abs(factor.title_delta) >= 0.01) return `${playoff}, ${simFormatPointsSwing(factor.title_delta)} title odds`;
  return playoff;
}

export function simFactorsIntro(factors: readonly SimSwingFactor[]): string {
  return factors.length > 0
    ? "The games and moves that move your odds most, found by replaying the same seasons with and without them."
    : "Nothing stands out: no single game or move moves your odds much right now.";
}

/**
 * Shared PLAYER CARD model: pure, import-free, byte-identical twin of
 * mobile/src/lib/playerCard.ts. One place decides what a player card says
 * (status chips, game line, projection trend, progress) so the web and app
 * renderers (components/PlayerCardKit) only lay it out. See docs/player-card.md.
 */

export type PlayerCardVariant = "compact" | "matchup" | "card" | "list";

/** Avatar scale tokens: every player card of a given variant uses the same photo size. */
export const PLAYER_CARD_AVATAR_SIZE: Record<PlayerCardVariant, number> = {
  compact: 32,
  matchup: 40,
  card: 56,
  /** Dense list row (PlayerListRow); the `compact` density uses 32. */
  list: 40,
};

export type PlayerGameStatus = "scheduled" | "in_progress" | "final";
export type ChipTone = "success" | "danger" | "warning" | "muted" | "accent";
export type PlayerChipKind = "live" | "final" | "upcoming" | "bye" | "out" | "questionable" | "doubtful";

export interface PlayerStatusChip {
  kind: PlayerChipKind;
  label: string;
  tone: ChipTone;
}

/** The slice of a Matchup starter (suggested or real) a card reads. */
export interface PlayerCardSource {
  player_id?: string | null;
  name?: string | null;
  position?: string | null;
  team?: string | null;
  tier?: string | null;
  slot?: string | null;
  injury_label?: string | null;
  injury_status?: string | null;
  overall_rating?: number | null;
  actual_points?: number | null;
  game_started?: boolean | null;
  game_status?: PlayerGameStatus | null;
  game_final?: boolean | null;
  game_kickoff_at?: string | null;
  game_opponent?: string | null;
  game_is_home?: boolean | null;
  game_team_score?: number | null;
  game_opponent_score?: number | null;
  game_progress?: number | null;
  projected_final?: number | null;
  projection?: { status: string; point_estimate: number | null; opponent?: string | null } | null;
}

export interface PlayerCardModel {
  playerId: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier: string | null;
  slot: string | null;
  injuryLabel: string;
  overallRating: number | null;
  gameStatus: PlayerGameStatus | null;
  /** Real points scored (only once his game has started). */
  points: number | null;
  /** This week's pre-game projection. */
  projection: number | null;
  /** Live projected final (in-progress games only). */
  projectedFinal: number | null;
  /** Best end-of-game number: final points, live projected final, or the projection. */
  expectedFinal: number | null;
  /** Share (0-1) of his game played; 1 final, 0 not started. */
  progress: number;
  opponent: string | null;
  isHome: boolean | null;
  kickoffAt: string | null;
  teamScore: number | null;
  opponentScore: number | null;
  bye: boolean;
  out: boolean;
  doubtful: boolean;
  questionable: boolean;
}

const OUT_LABELS = new Set(["out", "o", "ir", "injured reserve", "pup", "nfi", "non-football injury", "sus", "susp", "suspended", "inactive", "covid", "covid-19"]);
const DOUBTFUL_LABELS = new Set(["doubtful", "d"]);
const QUESTIONABLE_LABELS = new Set(["questionable", "q", "day-to-day", "day to day", "dtd"]);

function norm(label: string | null | undefined): string {
  return (label ?? "").trim().toLowerCase();
}

export function injuryFlags(label: string | null | undefined): { out: boolean; doubtful: boolean; questionable: boolean } {
  const key = norm(label);
  return { out: OUT_LABELS.has(key), doubtful: DOUBTFUL_LABELS.has(key), questionable: QUESTIONABLE_LABELS.has(key) };
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveStatus(source: PlayerCardSource): PlayerGameStatus | null {
  if (source.game_status) return source.game_status;
  if (source.game_final === true) return "final";
  if (source.game_started === true) return "in_progress";
  if (source.game_started === false) return "scheduled";
  return null;
}

/** Build the card model for one Matchup starter (suggested or real). */
export function playerCardFromStarter(source: PlayerCardSource): PlayerCardModel {
  const flags = injuryFlags(source.injury_label || source.injury_status);
  const status = resolveStatus(source);
  const started = status === "in_progress" || status === "final" || source.game_started === true;
  const projectionRow = source.projection ?? null;
  const bye = projectionRow?.status === "bye_week";
  // A player ruled out is not projected any points this week, same as a bye (he only has points if his game already started).
  const startedNow = status === "in_progress" || status === "final" || source.game_started === true;
  const projection = projectionRow?.status === "ok" && !(flags.out && !startedNow) ? num(projectionRow.point_estimate) : null;
  const actual = num(source.actual_points);
  const points = started && actual != null ? actual : null;
  const projectedFinal = status === "in_progress" ? num(source.projected_final) : null;
  let expectedFinal: number | null;
  if (bye || (flags.out && !startedNow)) expectedFinal = 0;
  else if (status === "final") expectedFinal = points;
  else if (status === "in_progress") expectedFinal = projectedFinal ?? points ?? projection;
  else expectedFinal = projection;
  const rawProgress = num(source.game_progress);
  const progress = status === "final" ? 1 : status === "in_progress" ? Math.min(1, Math.max(0, rawProgress ?? 0)) : 0;
  return {
    playerId: source.player_id ?? null,
    name: (source.name ?? "").trim() || "Unknown player",
    position: source.position ?? null,
    team: source.team ?? null,
    tier: source.tier ?? null,
    slot: source.slot ?? null,
    injuryLabel: (source.injury_label ?? "").trim(),
    overallRating: num(source.overall_rating),
    gameStatus: status,
    points,
    projection,
    projectedFinal,
    expectedFinal,
    progress,
    opponent: source.game_opponent ?? projectionRow?.opponent ?? null,
    isHome: typeof source.game_is_home === "boolean" ? source.game_is_home : null,
    kickoffAt: source.game_kickoff_at ?? null,
    teamScore: num(source.game_team_score),
    opponentScore: num(source.game_opponent_score),
    bye,
    out: flags.out,
    doubtful: flags.doubtful,
    questionable: flags.questionable,
  };
}

/**
 * Chips for the card's status area. Primary (always one): BYE, OUT, LIVE,
 * FINAL or UPCOMING (no chip when his game state is unknown). Secondary:
 * QUESTIONABLE / DOUBTFUL when he is not already OUT.
 */
export function playerStatusChips(model: PlayerCardModel): PlayerStatusChip[] {
  const chips: PlayerStatusChip[] = [];
  if (model.bye) chips.push({ kind: "bye", label: "BYE", tone: "warning" });
  else if (model.out) chips.push({ kind: "out", label: "OUT", tone: "danger" });
  else if (model.gameStatus === "in_progress") chips.push({ kind: "live", label: "LIVE", tone: "success" });
  else if (model.gameStatus === "final") chips.push({ kind: "final", label: "FINAL", tone: "muted" });
  else if (model.gameStatus === "scheduled") chips.push({ kind: "upcoming", label: "UPCOMING", tone: "accent" });
  if (!model.out && !model.bye) {
    if (model.doubtful) chips.push({ kind: "doubtful", label: "DOUBTFUL", tone: "danger" });
    else if (model.questionable) chips.push({ kind: "questionable", label: "QUESTIONABLE", tone: "warning" });
  }
  return chips;
}

export interface ProjectionTrend {
  dir: "up" | "down" | "flat";
  delta: number;
}

/** Trend of his live/final outcome against his pre-game projection; null when either is unknown or the game has not started. */
export function trendVsProjection(model: PlayerCardModel, flatBand = 1): ProjectionTrend | null {
  if (model.gameStatus !== "in_progress" && model.gameStatus !== "final") return null;
  const outcome = model.gameStatus === "final" ? model.points : model.projectedFinal;
  if (outcome == null || model.projection == null) return null;
  const delta = Math.round((outcome - model.projection) * 10) / 10;
  return { dir: Math.abs(delta) < flatBand ? "flat" : delta > 0 ? "up" : "down", delta };
}

/** "Sun 1:00 PM" in the viewer's time zone (or the given one). */
export function kickoffLabel(kickoffAt: string | null | undefined, timeZone?: string): string | null {
  if (!kickoffAt) return null;
  const date = new Date(kickoffAt);
  if (Number.isNaN(date.getTime())) return null;
  try {
    return date.toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone });
  } catch {
    return null;
  }
}

/** Rough quarter from wall-clock progress. There is no live game clock in our data, so this is always an estimate ("~Q3"). */
export function estimatedQuarter(progress: number): string {
  if (progress >= 0.99) return "~Q4";
  const quarter = Math.min(4, Math.max(1, Math.ceil(progress * 4)));
  return `~Q${quarter}`;
}

/** The team/opponent line: "@ DAL · Sun 1:00 PM", "vs DAL · ~Q3", "vs DAL · Final 24-17 W", "Bye week". */
export function playerGameLine(model: PlayerCardModel, timeZone?: string): string {
  if (model.bye) return "Bye week";
  const versus = model.opponent ? `${model.isHome === false ? "@" : "vs"} ${model.opponent}` : null;
  let tail: string | null = null;
  if (model.gameStatus === "in_progress") tail = estimatedQuarter(model.progress);
  else if (model.gameStatus === "final") {
    if (model.teamScore != null && model.opponentScore != null) {
      const result = model.teamScore > model.opponentScore ? "W" : model.teamScore < model.opponentScore ? "L" : "T";
      tail = `Final ${Math.round(model.teamScore)}-${Math.round(model.opponentScore)} ${result}`;
    } else tail = "Final";
  } else if (model.gameStatus === "scheduled") tail = kickoffLabel(model.kickoffAt, timeZone);
  return [versus, tail].filter(Boolean).join(" · ") || (model.team ?? "");
}

/** One-decimal points text ("12.4") or an em dash. */
export function formatCardPoints(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

/** Big number for the matchup card: live/final points once started, else the projection, else null (bye/unknown). */
export function headlinePoints(model: PlayerCardModel): { value: number | null; kind: "pts" | "proj" | null } {
  if (model.bye) return { value: null, kind: null };
  if (model.points != null && (model.gameStatus === "in_progress" || model.gameStatus === "final")) {
    return { value: model.points, kind: "pts" };
  }
  if (model.projection != null) return { value: model.projection, kind: "proj" };
  return { value: null, kind: null };
}

/** Screen-reader summary of a matchup card. */
export function playerCardAriaLabel(model: PlayerCardModel): string {
  const head = headlinePoints(model);
  const parts = [model.name, model.position, model.team].filter(Boolean) as string[];
  for (const chip of playerStatusChips(model)) parts.push(chip.label.toLowerCase());
  if (head.value != null) parts.push(`${head.value.toFixed(1)} ${head.kind === "pts" ? "points" : "projected"}`);
  if (model.projectedFinal != null) parts.push(`projected final ${model.projectedFinal.toFixed(1)}`);
  return parts.join(", ");
}

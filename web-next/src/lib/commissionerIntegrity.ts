/**
 * League integrity (Commissioner section) presentation, shared by web and the app.
 * The block between the SHARED markers is byte-identical to
 * mobile/src/lib/commissionerIntegrity.ts (a mobile test compares them): edit
 * both together. Pure TS, no imports, so node --test can run it. Engine and
 * thresholds: modules/league_integrity.py, docs/commissioner-tools.md.
 */

// SHARED BEGIN
export type IntegrityBand = "fine" | "worth_a_look" | "strong" | "not_enough_data";
export type DraftOrderRule = "unknown" | "record" | "lottery";

export interface IntegrityEvidence {
  kind: "lineup" | "roster" | "persistence" | "context";
  week: number | null;
  text: string;
}

export interface IntegritySeriesPoint {
  week: number;
  actual: number;
  best_possible: number;
  efficiency: number | null;
  flagged: boolean;
}

export interface IntegrityTeam {
  roster_id: number;
  team_name: string;
  owner_name: string;
  band: IntegrityBand;
  band_label: string;
  score: number;
  confidence: "low" | "medium" | "high";
  interpretation: "none" | "possible_tanking" | "possible_inactivity" | "possible_resting" | "unclear";
  context: "eliminated" | "clinched" | "alive" | "unknown";
  weeks: { evaluated: number; flagged: number; longest_streak: number; latest_streak: number };
  evidence: IntegrityEvidence[];
  innocent_explanations: string[];
  series: IntegritySeriesPoint[];
}

export type IntegrityTradePattern = "lopsided" | "round_trip" | "burst";

export interface IntegrityCollusionPair {
  roster_ids: number[];
  beneficiary_name: string;
  giver_name: string;
  headline: string;
  summary: string;
  patterns: IntegrityTradePattern[];
  trades_between: number;
  lopsided_same_direction: number;
  band: IntegrityBand;
  band_label: string;
  confidence: "low" | "medium" | "high";
  evidence: string[];
  innocent_explanations: string[];
}

export interface IntegrityInactiveManager {
  roster_id: number;
  team_name: string;
  owner_name: string;
  evidence: string[];
  innocent_explanations: string[];
}

export interface IntegrityCalendar {
  trade_deadline_week: number | null;
  current_week: number | null;
  trade_deadline_passed: boolean;
  weeks_to_deadline: number | null;
  deadline_phase: "none" | "open" | "final_week" | "passed";
  playoff_week_start: number | null;
  regular_season_weeks: number | null;
  in_season: boolean;
}

export interface CommissionerIntegrityResponse {
  ok: boolean;
  reason: string;
  is_premium?: boolean;
  upsell?: { title: string; body: string } | null;
  draft_order_rule?: DraftOrderRule;
  weeks_evaluated?: number;
  last_week?: number;
  week?: number | null;
  teams: IntegrityTeam[];
  collusion: IntegrityCollusionPair[];
  inactive: IntegrityInactiveManager[];
  summary?: Record<IntegrityBand, number>;
  limits?: string[];
  calendar?: IntegrityCalendar | null;
}

export const DRAFT_ORDER_OPTIONS: { value: DraftOrderRule; label: string }[] = [
  { value: "unknown", label: "Not sure" },
  { value: "record", label: "Worst record picks first" },
  { value: "lottery", label: "Lottery / other" },
];

export type IntegrityTone = "success" | "warning" | "danger" | "muted";

/** Semantic tone per band: green fine, amber look, red strong, grey not enough. */
export function bandTone(band: IntegrityBand): IntegrityTone {
  if (band === "strong") return "danger";
  if (band === "worth_a_look") return "warning";
  if (band === "fine") return "success";
  return "muted";
}

export const BAND_LABEL: Record<IntegrityBand, string> = {
  fine: "Lineup looks fine",
  worth_a_look: "Worth a look",
  strong: "Strong signals",
  not_enough_data: "Not enough weeks yet",
};

/** Reason codes the server returns instead of teams, in plain words. */
const REASON_MESSAGES: Record<string, string> = {
  unsupported_platform: "League integrity is only available for Sleeper leagues for now.",
  offseason: "League integrity needs played weeks. It opens once the regular season is under way.",
  not_enough_weeks: "Not enough weeks yet. Signals need at least three completed regular-season weeks.",
  best_ball: "Best-ball leagues set lineups automatically, so there are no lineup decisions to check.",
  no_lineup_data: "Sleeper has no saved lineup history for this league yet.",
  no_roster_in_league: "We could not match your Sleeper account to a team in this league.",
};

export function integrityReasonMessage(reason: string): string {
  return REASON_MESSAGES[reason] || "League integrity is not available for this league right now.";
}

export const INTERPRETATION_LABEL: Record<IntegrityTeam["interpretation"], string> = {
  none: "",
  possible_tanking: "Pattern fits tanking",
  possible_inactivity: "Pattern fits inactivity or mismanagement",
  possible_resting: "Pattern fits resting after clinching",
  unclear: "Context unclear",
};

export const CONFIDENCE_LABEL: Record<"low" | "medium" | "high", string> = {
  low: "Low confidence",
  medium: "Medium confidence",
  high: "High confidence",
};

/** Teams worth the commissioner's attention first; the rest collapse. */
export function splitTeams(teams: IntegrityTeam[]): { flagged: IntegrityTeam[]; rest: IntegrityTeam[] } {
  const flagged = teams.filter((t) => t.band === "strong" || t.band === "worth_a_look");
  const rest = teams.filter((t) => t.band !== "strong" && t.band !== "worth_a_look");
  return { flagged, rest };
}

/** One calm sentence for the top of the page. */
export function integritySummaryLine(resp: CommissionerIntegrityResponse): string {
  const weeks = resp.weeks_evaluated ?? 0;
  const { flagged } = splitTeams(resp.teams);
  const extras = resp.collusion.length + resp.inactive.length;
  if (flagged.length === 0 && extras === 0) {
    return `No team stands out after ${weeks} week${weeks === 1 ? "" : "s"}. Lineups look normal.`;
  }
  const parts: string[] = [];
  if (flagged.length) parts.push(`${flagged.length} team${flagged.length === 1 ? "" : "s"} worth a look`);
  if (resp.collusion.length) parts.push(`${resp.collusion.length} trade pair${resp.collusion.length === 1 ? "" : "s"} worth a look`);
  if (resp.inactive.length) parts.push(`${resp.inactive.length} possibly inactive manager${resp.inactive.length === 1 ? "" : "s"}`);
  return `After ${weeks} week${weeks === 1 ? "" : "s"}: ${parts.join(", ")}. These are prompts to check, not conclusions.`;
}
/** Short summary for the teams with no flag, so a clean league is one line, not a wall of identical cards. */
export function restSummary(teams: IntegrityTeam[], flaggedCount: number): string {
  const { rest } = splitTeams(teams);
  if (!rest.length) return "";
  const fine = rest.filter((t) => t.band === "fine").length;
  const early = rest.length - fine;
  if (flaggedCount === 0 && early === 0) return `All ${teams.length} teams look fine this week`;
  const head = fine === 1 ? "1 other team looks fine this week" : `${fine} other teams look fine this week`;
  return early ? `${head}; ${early} without enough weeks yet` : head;
}

/** League calendar facts (trade deadline, playoffs) as short lines; never guessed, only what Sleeper settings say. */
export function calendarLines(cal: IntegrityCalendar | null | undefined): string[] {
  if (!cal) return [];
  const lines: string[] = [];
  if (cal.current_week && cal.in_season) lines.push(`Week ${cal.current_week} now`);
  const d = cal.trade_deadline_week;
  if (d == null) {
    lines.push("No trade deadline set");
  } else if (cal.deadline_phase === "passed") {
    lines.push(`Trade deadline passed (after week ${d}); trades reopen after the season`);
  } else if (cal.deadline_phase === "final_week") {
    lines.push(`Trade deadline is this week (week ${d}): last call`);
  } else if (cal.deadline_phase === "open" && cal.weeks_to_deadline != null) {
    const n = cal.weeks_to_deadline;
    lines.push(`Trade deadline: after week ${d} (${n} week${n === 1 ? "" : "s"} left)`);
  } else {
    lines.push(`Trade deadline: after week ${d}`);
  }
  if (cal.playoff_week_start) lines.push(`Playoffs start week ${cal.playoff_week_start}`);
  return lines;
}
// ---- Trade veto calculator (modules/trade_veto.py, docs/commissioner-tools.md) ----
export type VetoBand = "fair" | "explainable" | "lopsided" | "outrage";
export type VetoStatus = "ok" | "locked" | "invalid" | "unavailable" | "error" | "unsupported_platform";
export type VetoPosture = "contender" | "retool" | "rebuild";

export interface VetoSide {
  roster_id: number;
  team_name: string;
  posture: VetoPosture | string;
  /** Server's own label and standing for this team (the keys above are not the only ones). */
  posture_label?: string;
  record?: string;
  standing?: string;
  sends: string[];
  receives: string[];
  market_delta: number;
  team_score: number;
  points_per_week: number;
  worst_position: { position: string; per_week_delta: number } | null;
  confidence?: string | null;
}

export interface VetoCheckResponse {
  ok: boolean;
  is_premium?: boolean;
  upsell?: { title: string; body: string } | null;
  status: VetoStatus;
  headline?: string;
  sides?: VetoSide[];
  outrage?: number;
  band?: VetoBand;
  label?: string;
  advice?: string;
  explained_by_roster?: boolean;
  hurt_roster_id?: string;
  reasons?: string[];
  history_points?: number;
  limits?: string[];
}

export interface VetoCheckRequest {
  roster_a: number;
  roster_b: number;
  a_sends_player_ids: string[];
  b_sends_player_ids: string[];
  a_sends_pick_ids: string[];
  b_sends_pick_ids: string[];
  lens: string;
}

export const VETO_BAND_LABEL: Record<VetoBand, string> = {
  fair: "Fair",
  explainable: "Uneven but explainable",
  lopsided: "Lopsided: worth a conversation",
  outrage: "Outrage-level: review before it processes",
};

/** Same fixed semantic tones as the integrity view; no new colors. */
export function vetoBandTone(band: VetoBand): IntegrityTone {
  if (band === "outrage") return "danger";
  if (band === "lopsided") return "warning";
  if (band === "fair") return "success";
  return "muted";
}

export const VETO_POSTURE_LABEL: Record<string, string> = {
  contender: "Contender",
  fringe_contender: "Fringe Contender",
  retool: "Retool",
  rebuild: "Rebuild",
  tank: "Tank/Rebuild",
};

export function vetoPostureLabel(posture: string | null | undefined): string {
  return VETO_POSTURE_LABEL[String(posture || "").toLowerCase()] || "";
}

/** The direction badge for a side: the server's label wins; a missing label never hides the badge. */
export function vetoSideDirection(side: { posture?: string | null; posture_label?: string | null }): string {
  return String(side.posture_label || "").trim() || vetoPostureLabel(side.posture);
}

/** Whole-number market change with an explicit sign, e.g. "+1,240" / "-310". */
export function formatSigned(n: number, digits = 0): string {
  const rounded = digits > 0 ? Number(n.toFixed(digits)) : Math.round(n);
  const text = Math.abs(rounded).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (rounded === 0) return text;
  return `${rounded > 0 ? "+" : "-"}${text}`;
}

/** Lineup change for one side, e.g. "Lineup -3.2 pts/wk". */
export function vetoPointsLine(side: Pick<VetoSide, "points_per_week">): string {
  return `Lineup ${formatSigned(side.points_per_week, 1)} pts/wk`;
}

/** Where the hit lands, or "" when no position is hurt. */
export function vetoWorstPositionLine(side: Pick<VetoSide, "worst_position">): string {
  const w = side.worst_position;
  if (!w || w.per_week_delta >= 0) return "";
  return `Biggest hit: ${w.position} (${formatSigned(w.per_week_delta, 1)} pts/wk)`;
}

/** Build the request body; empty trades are rejected client-side so the button can stay disabled. */
export function buildVetoRequest(input: {
  rosterA: number | string;
  rosterB: number | string;
  aPlayers: string[];
  bPlayers: string[];
  aPicks: string[];
  bPicks: string[];
  lens?: string;
}): VetoCheckRequest | null {
  if (String(input.rosterA).trim() === "" || String(input.rosterB).trim() === "") return null;
  const a = Number(input.rosterA);
  const b = Number(input.rosterB);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return null;
  if (input.aPlayers.length + input.bPlayers.length + input.aPicks.length + input.bPicks.length === 0) return null;
  return {
    roster_a: a,
    roster_b: b,
    a_sends_player_ids: input.aPlayers,
    b_sends_player_ids: input.bPlayers,
    a_sends_pick_ids: input.aPicks,
    b_sends_pick_ids: input.bPicks,
    lens: input.lens || "Dynasty",
  };
}

/** True when the response carries a gradable result. */
export function vetoHasResult(resp: VetoCheckResponse | null | undefined): boolean {
  return !!resp && resp.status === "ok" && !!resp.band && Array.isArray(resp.sides) && resp.sides.length > 0;
}

/** Plain message for the non-ok statuses; the server headline wins when it sent one. */
export function vetoStatusMessage(resp: VetoCheckResponse): string {
  if (resp.headline) return resp.headline;
  if (resp.status === "unsupported_platform") return "The trade veto calculator is only available for Sleeper leagues for now.";
  if (resp.status === "unavailable") return "League data is not ready yet. Try again in a moment.";
  if (resp.status === "invalid") return "That trade could not be checked. Check the teams and assets and try again.";
  return "The check hit a problem. Try again in a moment.";
}
// SHARED END

/**
 * League integrity (Commissioner) presentation, shared by web and the app.
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

export interface IntegrityCollusionPair {
  roster_ids: number[];
  beneficiary_name: string;
  giver_name: string;
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

export interface CommissionerStatusResponse {
  ok: boolean;
  is_commissioner: boolean;
  reason: string;
}

export interface CommissionerIntegrityResponse {
  ok: boolean;
  reason: string;
  is_premium?: boolean;
  is_commissioner: boolean | null;
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
  not_commissioner: "League integrity is only shown to the league's commissioner.",
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
  if (resp.collusion.length) parts.push(`${resp.collusion.length} repeated lopsided trade pair${resp.collusion.length === 1 ? "" : "s"}`);
  if (resp.inactive.length) parts.push(`${resp.inactive.length} possibly inactive manager${resp.inactive.length === 1 ? "" : "s"}`);
  return `After ${weeks} week${weeks === 1 ? "" : "s"}: ${parts.join(", ")}. These are prompts to check, not conclusions.`;
}

/** Show the Commissioner entry only once the server confirmed commissioner status. */
export function showCommissionerEntry(status: CommissionerStatusResponse | null | undefined): boolean {
  return Boolean(status && status.ok && status.is_commissioner);
}
// SHARED END

/**
 * Multi-team (3 to 6 team) Trade Analyzer: pure presentation logic shared by
 * web and mobile. Byte-identical to mobile/src/lib/multiTeamTrade.ts (listed
 * in scripts/check_lib_twins.mjs IDENTICAL), so it has no imports.
 *
 * Wire contract: POST /v1/leagues/{id}/trade-analyzer/multi
 * (docs/multi-team-trade-api.md). A trade is a transfer matrix: a list of
 * {type, id, from_roster_id, to_roster_id}.
 *
 * Two separate surfaces read the same response:
 *  1. ANALYSIS (private, honest): one card per team, verdict, most hurt.
 *  2. SHARE (pitching the deal to other managers): persuasion framed, no
 *     scoreboard words and no red verdicts, but every team's real value change
 *     is still printed as a plain number (nothing hidden).
 */

export const MULTI_TEAM_MIN = 3;
export const MULTI_TEAM_MAX = 6;
export const MULTI_TEAM_MAX_TRANSFERS = 36;
/** From this many teams the analysis is a ranked list with tap to expand. */
export const RANKED_LIST_FROM = 5;
/** The share card draws a flow for this many teams, a list above it. */
export const SHARE_FLOW_MAX_TEAMS = 3;

export type MultiAssetType = "player" | "pick";

export interface MultiTransfer {
  type: MultiAssetType;
  id: string;
  from_roster_id: string;
  to_roster_id: string;
}

export interface MultiAsset {
  type: MultiAssetType;
  id: string;
  label: string;
  position: string;
  team: string;
  age?: number | null;
  score?: number | null;
  to_roster_id?: string;
  to_team_name?: string;
  from_roster_id?: string;
  from_team_name?: string;
}

export interface MultiWhy {
  factor: "flows" | "market" | "lineup" | "roster_fit" | "posture" | "risk" | string;
  text: string;
}

export interface MultiVetoRisk {
  outrage?: number;
  band?: string;
  label?: string;
  advice?: string;
  explained_by_roster?: boolean;
  reasons?: string[];
}

export interface MultiTeamVerdict {
  band?: string;
  ui_verdict?: string;
  confidence?: string;
  rationale?: string;
  value_delta?: number;
  tone?: string;
}

export type MultiTone = "accept" | "fair" | "counter" | "decline";
export type MultiOutcome = "wins" | "even" | "gives_up" | "loses";

export interface MultiTeamResult {
  roster_id: string;
  team_name: string;
  is_perspective: boolean;
  sends: MultiAsset[];
  receives: MultiAsset[];
  verdict: MultiTeamVerdict;
  trade_score: number;
  market_delta: number;
  lineup_delta: { per_week: number; ros?: number | null; worst_position?: string | null };
  tone: MultiTone | string;
  color_token?: string;
  outcome: MultiOutcome | string;
  posture?: { key?: string; group?: string; label?: string };
  roster_overflow?: { need?: number } | null;
  why: MultiWhy[];
  veto_risk: MultiVetoRisk | null;
}

export interface MultiRankingRow {
  rank: number;
  roster_id: string;
  team_name?: string | null;
  trade_score: number;
}

export interface MultiSummary {
  headline: string;
  team_count: number;
  balance: { id: "balanced" | "tilted" | "lopsided" | string; label: string; spread: number; best_roster_id: string; worst_roster_id: string };
  most_hurt_roster_id: string;
  best_off_roster_id: string;
  ranking: MultiRankingRow[];
  market_sum?: number;
  perspective?: { roster_id: string; outcome: string; rank: number; of: number } | null;
}

export interface MultiTradeError {
  code: string;
  message?: string;
}

export interface MultiTeamTradeResponse {
  ok?: boolean;
  status?: string;
  reason?: string;
  headline?: string;
  errors?: MultiTradeError[];
  team_count?: number;
  teams?: MultiTeamResult[];
  flows?: Array<MultiTransfer & { from_team_name?: string; to_team_name?: string }>;
  summary?: MultiSummary;
  counts_against_free_limit?: boolean;
  is_premium?: boolean;
  veto_locked?: boolean;
  veto_upsell?: { title?: string; body?: string } | null;
}

// ---------------------------------------------------------------------------
// Builder state -> request
// ---------------------------------------------------------------------------

/** One asset in the builder: where it is now and where it is going. */
export interface BuilderAsset {
  type: MultiAssetType;
  id: string;
  fromRosterId: string;
  /** Empty until the manager picks a destination. */
  toRosterId: string;
}

export function builderKey(asset: Pick<BuilderAsset, "type" | "id">): string {
  return `${asset.type}:${asset.id}`;
}

/** Add an asset (an asset can only move once: re-adding replaces it). */
export function upsertAsset(assets: BuilderAsset[], next: BuilderAsset): BuilderAsset[] {
  const key = builderKey(next);
  return [...assets.filter((a) => builderKey(a) !== key), next];
}

export function removeAsset(assets: BuilderAsset[], type: MultiAssetType, id: string): BuilderAsset[] {
  return assets.filter((a) => !(a.type === type && a.id === id));
}

/** Drop a team: its assets, and anything routed to it, go with it. */
export function removeTeam(participants: string[], assets: BuilderAsset[], rosterId: string) {
  return {
    participants: participants.filter((p) => p !== rosterId),
    assets: assets.filter((a) => a.fromRosterId !== rosterId && a.toRosterId !== rosterId),
  };
}

export function addTeam(participants: string[], rosterId: string): string[] {
  if (!rosterId || participants.includes(rosterId) || participants.length >= MULTI_TEAM_MAX) return participants;
  return [...participants, rosterId];
}

export type BuilderIssue =
  | { code: "too_few_teams"; message: string }
  | { code: "no_assets"; message: string }
  | { code: "unrouted"; message: string }
  | { code: "team_not_involved"; message: string; rosterId: string };

/** Why Analyze is not ready yet, in plain language ("" ready). */
export function builderIssue(participants: string[], assets: BuilderAsset[]): BuilderIssue | null {
  if (participants.length < MULTI_TEAM_MIN) {
    return { code: "too_few_teams", message: `Add at least ${MULTI_TEAM_MIN - participants.length === 1 ? "one more team" : `${MULTI_TEAM_MIN - participants.length} more teams`} (3 to 6 teams).` };
  }
  if (assets.length === 0) return { code: "no_assets", message: "Add the players and picks each team sends." };
  if (assets.some((a) => !a.toRosterId)) return { code: "unrouted", message: "Choose which team receives each asset." };
  const involved = new Set(assets.flatMap((a) => [a.fromRosterId, a.toRosterId]));
  const idle = participants.find((p) => !involved.has(p));
  if (idle) return { code: "team_not_involved", rosterId: idle, message: "Every team needs to send or receive something." };
  return null;
}

export function buildTransfers(assets: BuilderAsset[]): MultiTransfer[] {
  return assets
    .filter((a) => a.toRosterId)
    .map((a) => ({ type: a.type, id: a.id, from_roster_id: a.fromRosterId, to_roster_id: a.toRosterId }));
}

/** Teams in the builder, the signed-in manager's seat first. */
export function orderParticipants(participants: string[], myRosterId: string): string[] {
  return [...participants].sort((a, b) => (a === myRosterId ? -1 : b === myRosterId ? 1 : 0));
}

/** Sender -> receiver grid for the wide-screen matrix. */
export function buildMatrix(participants: string[], assets: BuilderAsset[]): Record<string, Record<string, BuilderAsset[]>> {
  const grid: Record<string, Record<string, BuilderAsset[]>> = {};
  for (const from of participants) {
    grid[from] = {};
    for (const to of participants) grid[from][to] = [];
  }
  for (const asset of assets) {
    if (!asset.toRosterId || !grid[asset.fromRosterId]) continue;
    grid[asset.fromRosterId][asset.toRosterId]?.push(asset);
  }
  return grid;
}

// ---------------------------------------------------------------------------
// Errors in plain language
// ---------------------------------------------------------------------------

const ERROR_COPY: Record<string, string> = {
  invalid_transfer: "One of the moves in this trade is incomplete. Check each asset has a sender and a receiver.",
  empty_trade: "Add the players and picks each team sends.",
  too_few_teams: "A multi-team trade needs at least 3 teams.",
  too_many_teams: "A multi-team trade can include at most 6 teams.",
  too_many_transfers: "That is too many assets for one trade (36 is the most). Remove a few.",
  same_team: "A team cannot send an asset to itself. Pick a different receiver.",
  unknown_roster: "One of the teams is not in this league.",
  asset_not_owned: "A player or pick is no longer on the team you sent it from. Remove it and try again.",
  asset_moved_twice: "An asset can only move once in a trade. Remove the duplicate.",
  unknown_pick: "We could not find one of the draft picks. Remove it and try again.",
};

/** Each API error mapped to a sentence a manager can act on. */
export function multiTradeErrorMessages(errors: MultiTradeError[] | undefined | null): string[] {
  const out: string[] = [];
  for (const error of errors ?? []) {
    const text = ERROR_COPY[error.code] ?? (error.message ? error.message : "This trade is not valid.");
    // The server names the asset and teams; keep that detail after the advice.
    const detail = ERROR_COPY[error.code] && error.message && !out.includes(error.message) ? ` (${error.message.replace(/[.]$/, "")})` : "";
    const line = `${text}${detail}`;
    if (!out.includes(line)) out.push(line);
  }
  return out;
}

const REASON_COPY: Record<string, string> = {
  unavailable: "Values or draft picks are not ready for this league yet. Try again in a bit.",
  unsupported_platform: "Multi-team trades are available for Sleeper leagues. Use the standard Trade Analyzer for two teams.",
  no_sleeper_username_linked: "Link your Sleeper account and join this league from Home before evaluating a trade.",
  sleeper_user_not_found: "Link your Sleeper account and join this league from Home before evaluating a trade.",
  not_a_member_of_league: "Link your Sleeper account and join this league from Home before evaluating a trade.",
  espn_team_not_selected: "We don't know which team is yours in this league. Add it again from Add a league and pick your team.",
  empty_roster: "Your roster in this league looks empty, so there is nothing to trade from yet.",
  no_player_data: "Player data isn't available right now. Try again in a bit.",
};

/** Plain-language lines for any non-ok response (errors win over reason). */
export function multiTradeFailureLines(response: Pick<MultiTeamTradeResponse, "status" | "reason" | "errors" | "headline">): string[] {
  const fromErrors = multiTradeErrorMessages(response.errors);
  if (fromErrors.length) return fromErrors;
  const reason = response.reason ?? "";
  if (REASON_COPY[reason]) return [REASON_COPY[reason]];
  if (response.status && REASON_COPY[response.status]) return [REASON_COPY[response.status]];
  if (response.headline) return [response.headline];
  return ["Could not analyze this trade."];
}

export function isMultiTradeOk(response: MultiTeamTradeResponse | null | undefined): response is MultiTeamTradeResponse & { teams: MultiTeamResult[]; summary: MultiSummary } {
  return Boolean(response && response.status === "ok" && response.teams?.length && response.summary);
}

// ---------------------------------------------------------------------------
// Analysis (private, honest)
// ---------------------------------------------------------------------------

export type SemanticTone = "success" | "neutral" | "warning" | "danger";

/** Fixed semantic color per verdict tone (never a new token). */
export function toneSemantic(tone: string | undefined | null): SemanticTone {
  if (tone === "accept") return "success";
  if (tone === "counter") return "warning";
  if (tone === "decline") return "danger";
  return "neutral";
}

/** Fixed semantic color for a veto-risk band (trade_veto: fair, explainable, lopsided, outrage). */
export function vetoTone(band: string | undefined | null): SemanticTone {
  if (band === "outrage") return "danger";
  if (band === "lopsided") return "warning";
  if (band === "explainable") return "neutral";
  return "success";
}

const OUTCOME_LABEL: Record<string, string> = { wins: "Comes out ahead", even: "Fair deal", gives_up: "Gives up some value", loses: "Comes out behind" };

/** Short verdict chip text for a team. */
export function verdictChipLabel(team: Pick<MultiTeamResult, "verdict" | "outcome">): string {
  const ui = (team.verdict?.ui_verdict ?? "").trim();
  return ui || OUTCOME_LABEL[team.outcome] || "Fair deal";
}

export function formatSigned(value: number | null | undefined): string {
  const n = Math.round(Number(value) || 0);
  if (n === 0) return "0";
  return `${n > 0 ? "+" : "-"}${Math.abs(n).toLocaleString("en-US")}`;
}

/** Signed lineup points: one decimal under 10, none above. */
export function formatLineupPoints(points: number): string {
  const rounded = Math.abs(points) < 10 ? Math.round(points * 10) / 10 : Math.round(points);
  return `${rounded > 0 ? "+" : rounded < 0 ? "-" : ""}${Math.abs(rounded)}`;
}

export function lineupEffectText(team: Pick<MultiTeamResult, "lineup_delta">): string {
  const perWeek = Number(team.lineup_delta?.per_week) || 0;
  if (Math.abs(perWeek) < 0.05) return "No change to the weekly lineup";
  const ros = team.lineup_delta?.ros;
  const rosText = ros != null && Math.abs(Number(ros)) >= 1 ? `, ${formatLineupPoints(Number(ros))} rest of season` : "";
  return `${formatLineupPoints(perWeek)} pts a week in the lineup${rosText}`;
}

/** The 2 or 3 reasons worth showing: lineup, roster fit, posture and market first, flows last. */
export function topReasons(team: Pick<MultiTeamResult, "why">, max = 3): MultiWhy[] {
  const order = ["market", "lineup", "roster_fit", "posture", "risk"];
  const picked: MultiWhy[] = [];
  for (const factor of order) {
    const hit = team.why.find((w) => w.factor === factor && !picked.includes(w));
    if (hit) picked.push(hit);
    if (picked.length >= max) break;
  }
  return picked;
}

/** The flow sentence ("receives X and sends Y") for the expanded view. */
export function flowReason(team: Pick<MultiTeamResult, "why">): string {
  return team.why.find((w) => w.factor === "flows")?.text ?? "";
}

export function analysisLayout(teamCount: number): "stack" | "ranked" {
  return teamCount >= RANKED_LIST_FROM ? "ranked" : "stack";
}

export function teamById(teams: MultiTeamResult[], rosterId: string | undefined): MultiTeamResult | undefined {
  return teams.find((t) => t.roster_id === rosterId);
}

export function mostHurtBanner(response: Pick<MultiTeamTradeResponse, "teams" | "summary">): { headline: string; balance: string; mostHurtName: string | null; balanced: boolean } {
  const summary = response.summary;
  const hurt = summary ? teamById(response.teams ?? [], summary.most_hurt_roster_id) : undefined;
  const balanced = summary?.balance.id === "balanced";
  return {
    headline: balanced || !hurt ? "No team is clearly hurt" : `Most hurt: ${hurt.team_name}`,
    balance: summary?.balance.label ?? "",
    mostHurtName: balanced || !hurt ? null : hurt.team_name,
    balanced,
  };
}

/** Teams in the order the analysis shows them: stack = your team first then
 * the order named, ranked = best to worst by the server's ranking. */
export function analysisOrder(response: Pick<MultiTeamTradeResponse, "teams" | "summary">): MultiTeamResult[] {
  const teams = response.teams ?? [];
  if (analysisLayout(teams.length) === "stack") return teams;
  const rank = new Map((response.summary?.ranking ?? []).map((r) => [String(r.roster_id), r.rank]));
  return [...teams].sort((a, b) => (rank.get(a.roster_id) ?? 99) - (rank.get(b.roster_id) ?? 99));
}

/** One-line receives/sends summary for collapsed rows. */
export function assetsLine(assets: MultiAsset[], empty = "nothing"): string {
  return assets.map((a) => a.label).join(", ") || empty;
}

// ---------------------------------------------------------------------------
// Share (persuasion framed)
// ---------------------------------------------------------------------------

export interface ShareEdge {
  fromName: string;
  toName: string;
  fromRosterId: string;
  toRosterId: string;
  labels: string[];
}

export interface ShareTeam {
  rosterId: string;
  name: string;
  /** What this team gets, best first. */
  gets: MultiAsset[];
  /** What this team sends, with the receiver. */
  sends: MultiAsset[];
  /** Which needs the incoming assets fill (plain, supported facts only). */
  needs: string[];
  /** Plain true value change, signed. Shown for every team. */
  valueChange: number;
  valueChangeText: string;
  /** Set when the team gives up value: what it gets back. */
  getsBack: string;
}

export interface ShareModel {
  layout: "flow" | "list";
  headline: string;
  teams: ShareTeam[];
  edges: ShareEdge[];
}

const byScoreDesc = (a: MultiAsset, b: MultiAsset) => (Number(b.score) || 0) - (Number(a.score) || 0);

/** Needs the incoming assets fill, from facts on screen: positions received
 * that the team does not also send, and a lineup gain when there is one. */
export function shareNeeds(team: MultiTeamResult): string[] {
  const out: string[] = [];
  const sentPositions = new Set(team.sends.filter((a) => a.type === "player").map((a) => a.position));
  const gained: string[] = [];
  for (const asset of [...team.receives].sort(byScoreDesc)) {
    if (asset.type !== "player" || !asset.position || sentPositions.has(asset.position) || gained.includes(asset.position)) continue;
    gained.push(asset.position);
  }
  const perWeek = Number(team.lineup_delta?.per_week) || 0;
  if (gained.length && perWeek >= 0.5) out.push(`Adds ${gained.slice(0, 2).join(" and ")} to the starting lineup (${formatLineupPoints(perWeek)} pts a week)`);
  else if (gained.length) out.push(`Adds ${gained.slice(0, 2).join(" and ")} depth`);
  const picks = team.receives.filter((a) => a.type === "pick");
  if (picks.length) out.push(picks.length === 1 ? `Adds ${picks[0].label}` : `Adds ${picks.length} draft picks`);
  return out.slice(0, 2);
}

/** For a team giving up value: the best things it gets back. */
export function shareGetsBack(team: MultiTeamResult): string {
  if (Number(team.market_delta) >= 0) return "";
  const best = [...team.receives].sort(byScoreDesc).slice(0, 2);
  if (!best.length) return "";
  const starter = best.find((a) => a.type === "player");
  const pick = best.find((a) => a.type === "pick");
  const parts: string[] = [];
  if (starter) parts.push(`${starter.label}${starter.position ? ` (${starter.position})` : ""}`);
  if (pick) parts.push(pick.label);
  return parts.length ? `Gets back ${parts.join(" and ")}` : "";
}

export function buildShareModel(response: Pick<MultiTeamTradeResponse, "teams" | "flows">): ShareModel {
  const teams = response.teams ?? [];
  const edgeMap = new Map<string, ShareEdge>();
  for (const team of teams) {
    for (const asset of team.sends) {
      const to = asset.to_roster_id ?? "";
      const key = `${team.roster_id}>${to}`;
      const edge = edgeMap.get(key) ?? { fromName: team.team_name, toName: asset.to_team_name ?? "", fromRosterId: team.roster_id, toRosterId: to, labels: [] };
      edge.labels.push(asset.label);
      edgeMap.set(key, edge);
    }
  }
  const shareTeams: ShareTeam[] = teams.map((team) => ({
    rosterId: team.roster_id,
    name: team.team_name,
    gets: [...team.receives].sort(byScoreDesc),
    sends: team.sends,
    needs: shareNeeds(team),
    valueChange: Math.round(Number(team.market_delta) || 0),
    valueChangeText: formatSigned(team.market_delta),
    getsBack: shareGetsBack(team),
  }));
  return {
    layout: teams.length <= SHARE_FLOW_MAX_TEAMS ? "flow" : "list",
    headline: `${teams.length}-team trade`,
    teams: shareTeams,
    edges: [...edgeMap.values()],
  };
}

/** Share text: what each team gets first, then who sends what to whom. */
export function buildShareText(model: ShareModel, leagueName: string): string {
  const lines: string[] = [`${model.headline}${leagueName ? ` in ${leagueName}` : ""}`, ""];
  for (const team of model.teams) {
    const gets = team.gets.map((a) => a.label).join(", ") || "nothing";
    lines.push(`${team.name} gets ${gets}`);
    for (const need of team.needs) lines.push(`  ${need}`);
    if (team.getsBack) lines.push(`  ${team.getsBack}`);
    lines.push(`  Value change ${team.valueChangeText}`);
  }
  lines.push("", "Who sends what");
  for (const edge of model.edges) lines.push(`${edge.fromName} -> ${edge.toName}: ${edge.labels.join(", ")}`);
  return lines.join("\n");
}

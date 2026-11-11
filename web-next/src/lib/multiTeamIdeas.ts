/**
 * 3-team trade ideas (Trade Hub): pure presentation logic shared by web and
 * mobile. Byte-identical to mobile/src/lib/multiTeamIdeas.ts (listed in
 * scripts/check_lib_twins.mjs IDENTICAL), so it only has type imports.
 *
 * Wire contract: GET /v1/leagues/{id}/trade-ideas/multi
 * (docs/multi-team-trade-api.md). Every idea is a closed three-way deal where
 * each team's own verdict is Fair or better. An idea opens the multi-team
 * Analyzer prefilled (`?multi=` on web, `multiPrefill` on mobile) and the
 * Analyzer regrades it: nothing about value or verdict travels with the link.
 */
import type { MultiAsset, MultiTeamResult, MultiTeamTradeResponse, MultiTransfer } from "./multiTeamTrade";

const MAX_PREFILL_TRANSFERS = 36;
const PREFILL_FIELD_SEPARATOR = "~";

/** A team in an idea: the Analyzer's per-team result without veto risk (never computed for ideas). */
export type IdeaTeam = Omit<MultiTeamResult, "veto_risk">;

export interface MultiTeamIdea {
  id: string;
  headline: string;
  teams: IdeaTeam[];
  flows: Array<MultiTransfer & { from_team_name?: string; to_team_name?: string }>;
  partners: Array<{ roster_id: string; team_name: string }>;
  user: {
    roster_id: string;
    trade_score: number;
    market_delta: number;
    lineup_delta: { per_week: number; ros?: number | null; worst_position?: string | null };
    outcome: string;
  };
  summary: Partial<NonNullable<MultiTeamTradeResponse["summary"]>> & { headline?: string };
  /** Set when one added piece brought the last team to fair. */
  variant: { edits: number; note: string } | null;
  analyzer_request: { transfers: MultiTransfer[]; perspective_roster_id: string };
}

export interface MultiTeamIdeasResponse {
  ok?: boolean;
  reason?: string;
  message?: string;
  ideas: MultiTeamIdea[];
  /** Ideas found, also for Free (who sees only the count). */
  idea_count: number;
  locked: boolean;
  upsell?: { title?: string; body?: string } | null;
  is_premium?: boolean;
  search?: { partners?: number; candidates?: number; verified?: number; truncated?: boolean; reason?: string } | null;
}

export type IdeasSection =
  | { kind: "ideas"; ideas: MultiTeamIdea[] }
  | { kind: "locked"; count: number }
  | { kind: "empty"; message: string }
  | { kind: "closed"; message: string };

const EMPTY_COPY: Record<string, string> = {
  no_fit: "No three-way deal works for every team right now. Ideas appear when rosters move.",
  needs_unavailable: "We could not read every roster's needs yet. Try again in a moment.",
  league_too_small: "3-team ideas need a league with at least three teams.",
  unsupported_platform: "3-team ideas are for Sleeper leagues.",
  unavailable: "Player values are not ready yet. Try again in a moment.",
};

/** What the Trade Hub section shows for a response. */
export function ideasSection(response: MultiTeamIdeasResponse | null | undefined): IdeasSection {
  if (!response) return { kind: "empty", message: EMPTY_COPY.unavailable };
  if (response.reason && /deadline/i.test(response.reason)) {
    return { kind: "closed", message: response.message || "Trading is closed in your league right now." };
  }
  if (response.locked) return { kind: "locked", count: Math.max(0, Number(response.idea_count) || 0) };
  if (response.ideas?.length) return { kind: "ideas", ideas: response.ideas };
  return { kind: "empty", message: EMPTY_COPY[response.reason ?? "no_fit"] ?? EMPTY_COPY.no_fit };
}

export function lockedTeaserTitle(count: number): string {
  return count === 1 ? "1 three-team deal fits your league" : `${count} three-team deals fit your league`;
}

// ---------------------------------------------------------------------------
// Open the Analyzer prefilled
// ---------------------------------------------------------------------------

/** `type~from~to~id` per transfer, comma separated. `~` and `,` never occur in
 * a roster id, a player id or a pick id ("2027:1:3"), so no escaping is needed. */
export function encodePrefill(transfers: MultiTransfer[]): string {
  return transfers
    .slice(0, MAX_PREFILL_TRANSFERS)
    .map((t) => [t.type, t.from_roster_id, t.to_roster_id, t.id].join(PREFILL_FIELD_SEPARATOR))
    .join(",");
}

/** The transfers carried by a prefill string; malformed entries are dropped. */
export function decodePrefill(raw: string | null | undefined): MultiTransfer[] {
  const out: MultiTransfer[] = [];
  const seen = new Set<string>();
  for (const part of String(raw ?? "").split(",")) {
    const [type, from, to, ...rest] = part.split(PREFILL_FIELD_SEPARATOR);
    const id = rest.join(PREFILL_FIELD_SEPARATOR).trim();
    if ((type !== "player" && type !== "pick") || !from || !to || !id || from === to) continue;
    const key = `${type}:${id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ type, id, from_roster_id: from.trim(), to_roster_id: to.trim() });
    if (out.length >= MAX_PREFILL_TRANSFERS) break;
  }
  return out;
}

/** Builder state for a prefill: the participating teams (the viewer's seat
 * first, then the order they appear) and every asset routed. */
export function prefillToBuilder(transfers: MultiTransfer[], myRosterId: string) {
  const participants: string[] = [];
  for (const t of transfers) {
    for (const id of [t.from_roster_id, t.to_roster_id]) if (!participants.includes(id)) participants.push(id);
  }
  participants.sort((a, b) => (a === myRosterId ? -1 : b === myRosterId ? 1 : 0));
  return {
    participants,
    assets: transfers.map((t) => ({ type: t.type, id: t.id, fromRosterId: t.from_roster_id, toRosterId: t.to_roster_id })),
  };
}

/** Stable key so a prefill is applied once per idea. */
export function prefillKey(transfers: MultiTransfer[]): string {
  return transfers.map((t) => `${t.type}:${t.id}:${t.from_roster_id}>${t.to_roster_id}`).sort().join("|");
}

/** Web query string for the Analyzer: `?name=<league>&multi=<prefill>`. */
export function ideaAnalyzerQuery(leagueName: string, idea: Pick<MultiTeamIdea, "analyzer_request">): string {
  const params = new URLSearchParams({ name: leagueName });
  params.set("multi", encodePrefill(idea.analyzer_request.transfers));
  return params.toString().replace(/%2C/g, ",").replace(/%3A/g, ":").replace(/%7E/g, "~");
}

// ---------------------------------------------------------------------------
// Idea card
// ---------------------------------------------------------------------------

const labels = (assets: MultiAsset[]): string => assets.map((a) => a.label).join(", ") || "nothing";

export interface IdeaTeamLine {
  rosterId: string;
  name: string;
  isYou: boolean;
  tone: string;
  verdict: string;
  gets: string;
  sends: string;
  /** Signed value change, "+120" / "-80" / "0". */
  valueChange: string;
  /** The need this team's deal fills (the search's own reason), else the first reason. */
  why: string;
}

function signed(value: number | null | undefined): string {
  const n = Math.round(Number(value) || 0);
  return n > 0 ? `+${n}` : String(n);
}

/** One line per team for an idea card, the viewer's team first. */
export function ideaTeamLines(idea: MultiTeamIdea): IdeaTeamLine[] {
  return [...idea.teams]
    .sort((a, b) => Number(b.is_perspective) - Number(a.is_perspective))
    .map((team) => ({
      rosterId: team.roster_id,
      name: team.is_perspective ? "You" : team.team_name,
      isYou: team.is_perspective,
      tone: String(team.tone),
      verdict: team.verdict?.ui_verdict || (team.tone === "accept" ? "Good for them" : "Fair"),
      gets: labels(team.receives),
      sends: labels(team.sends),
      valueChange: signed(team.market_delta),
      why: team.why.find((w) => w.factor === "need")?.text || team.why[0]?.text || "",
    }));
}

/** An idea as the response shape the pitch card and share text already read. */
export function ideaAsResponse(idea: MultiTeamIdea): Pick<MultiTeamTradeResponse, "teams" | "flows"> {
  return { teams: idea.teams.map((t) => ({ ...t, veto_risk: null })), flows: idea.flows };
}

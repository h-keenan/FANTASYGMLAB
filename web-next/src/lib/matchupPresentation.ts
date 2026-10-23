/**
 * Matchup-specific presentation helpers — pure ports of small, PURE
 * composition functions from modules/web_matchup_ui.py (the real Streamlit
 * Matchup page's own data-assembly module) and mobile's MatchupScreen.tsx
 * (the reference client for GET .../leagues/{id}/matchup). No valuation,
 * projection, or lineup logic lives here — that's all already computed
 * server-side; these functions only decide how to format/color an
 * already-final value, the same tier of port myTeamPresentation.ts/
 * waiversPresentation.ts already are for their pages.
 */

import { notReadyReasonMessage } from "./notReadyMessages";
import { PLAIN_COPY } from "./experienceCopy";
import type {
  MatchupPositionEdge,
  MatchupRealStarter,
  MatchupResponse,
  MatchupSide,
  MatchupStarter,
  MatchupSuggestedMove,
  PlayerWeekProjection,
} from "./api";

/**
 * Matchup's own `reason` copy — byte-for-byte the same strings
 * modules/web_matchup_ui.py's NOT_READY_MESSAGES and mobile's
 * MatchupScreen.tsx NOT_READY_MESSAGES use for these reasons (both clients
 * agree, so this is the real, intentional copy, not a placeholder).
 * `not_a_member_of_league` and `empty_roster` are deliberately NOT routed
 * through lib/notReadyMessages.ts's shared "link your account" framing:
 * every other page (My Team/Trade Hub/Waivers) treats those the same as
 * "you haven't linked/joined yet," but Matchup's own ground-truth copy for
 * them is more specific ("you don't appear to own a team in this league" /
 * "this roster doesn't have any players yet") — overriding the shared
 * generic copy here preserves that distinction instead of flattening it.
 */
const MATCHUP_REASON_MESSAGES: Record<string, string> = {
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_current_week: "This league hasn't started a week yet.",
  no_matchup_data: "Sleeper doesn't have matchups posted for this week yet.",
  roster_not_in_matchups: "Your roster isn't in this week's matchup list.",
  bye_week: "You're not paired against anyone this week — enjoy the bye.",
  opponent_roster_missing: "Couldn't load your opponent's roster right now — try again in a bit.",
};

const DEFAULT_MATCHUP_MESSAGE = "Couldn't build this week's matchup for this league yet.";

/** `no_sleeper_username_linked` / `sleeper_user_not_found` / `no_player_data`
 * still resolve through the shared classification (same copy every other
 * page already uses for those three) — only the reasons above diverge. */
export function matchupReasonMessage(reason: string): string {
  const specific = MATCHUP_REASON_MESSAGES[reason];
  if (specific) return specific;
  const shared = notReadyReasonMessage(reason, {
    linkAccount: "Link your Sleeper account and join this league to see this week's matchup.",
  });
  return shared ?? DEFAULT_MATCHUP_MESSAGE;
}

export type MatchupNextAction = "retry" | "dashboard" | "connect";

/** The one next step for a Matchup dead end (the message itself is
 * matchupReasonMessage). Mirrored by mobile's matchupPresentation. */
export function matchupNextAction(reason: string): { action: MatchupNextAction; subtitle?: string } {
  switch (reason) {
    case "no_current_week":
      return { action: "dashboard", subtitle: PLAIN_COPY.matchupSeasonSubtitle };
    case "bye_week":
      return { action: "dashboard" };
    case "no_sleeper_username_linked":
    case "sleeper_user_not_found":
    case "not_a_member_of_league":
      return { action: "connect" };
    default:
      return { action: "retry" };
  }
}

export function matchupActionLabel(action: MatchupNextAction): string {
  if (action === "dashboard") return PLAIN_COPY.matchupDashboardAction;
  if (action === "connect") return PLAIN_COPY.matchupConnectAction;
  return PLAIN_COPY.matchupRetryAction;
}

export function recordLabel(side: MatchupSide): string {
  if (side.wins == null || side.losses == null) return "—";
  return `${side.wins}-${side.losses}${side.ties ? `-${side.ties}` : ""}`;
}

export function formatSeasonValue(value: number): string {
  return Math.round(value).toLocaleString();
}

/**
 * This week's per-game projection rendered as a short primary value +
 * caption — byte-for-byte the same statuses mobile's MatchupScreen.tsx
 * projectionDisplay renders text for (the only ones GET .../matchup's
 * trimmed PlayerWeekProjection can actually carry — see that type's own
 * comment on why `basis.opponent_defense_tier` isn't in scope here even
 * though the Streamlit-internal version of this note can reference it).
 */
export function projectionDisplay(
  projection: PlayerWeekProjection | null | undefined,
): { value: string | null; caption: string | null } {
  if (!projection) return { value: null, caption: null };
  if (projection.status === "ok" && projection.point_estimate != null) {
    return {
      value: `Proj ${projection.point_estimate.toFixed(1)}`,
      caption: projection.confidence ? `${projection.confidence} conf` : null,
    };
  }
  if (projection.status === "bye_week") return { value: "Bye week", caption: null };
  if (projection.status === "insufficient_player_data") return { value: "No projection yet", caption: null };
  if (projection.status === "no_opponent" || projection.status === "no_schedule_data") {
    return { value: "No matchup data", caption: null };
  }
  return { value: null, caption: null };
}

/**
 * Which number is this REAL starter row's PRIMARY/prominent figure.
 *
 * Before this player's own NFL game has kicked off, Sleeper's
 * `actual_points` is a real-looking `0.0` that isn't an actual result yet,
 * so leading with it reads as "this player scored zero" — misleading
 * (coridian_'s bug report, fixed on mobile first). This swaps the
 * hierarchy pre-kickoff: the projection becomes the prominent figure, and
 * the real score only takes over once `game_started` says this player's
 * specific game has actually begun — never just "the week is live"
 * (`MatchupSide.has_live_data`), since games across a week kick off at
 * different times. Byte-for-byte port of mobile's realStarterPointsDisplay.
 */
export function realStarterPointsDisplay(player: MatchupRealStarter): {
  value: string;
  caption: string | null;
  secondaryValue: string | null;
  secondaryCaption: string | null;
} {
  const projection = projectionDisplay(player.projection);
  const hasActual = player.actual_points != null;
  const started = player.game_started === true || (hasActual && player.actual_points! > 0);

  if (started) {
    return {
      value: hasActual ? player.actual_points!.toFixed(1) : "0.0",
      caption: "PTS",
      secondaryValue: projection.value,
      secondaryCaption: projection.caption,
    };
  }

  return {
    value: projection.value ?? "Not started",
    caption: projection.value ? projection.caption : null,
    secondaryValue: null,
    secondaryCaption: null,
  };
}

/**
 * `why` is server-composed as `" · "`-joined clauses in a fixed order —
 * tier, opportunity label, season-value rank-on-roster, injury note (see
 * `_matchup_starter_why` in services/mobile_api_service.py) — so the tier
 * and opportunity clauses can be stripped safely by position rather than by
 * fuzzy text matching. What's left (usually just the rank clause) becomes
 * the row's one-line supporting context. Byte-for-byte port of mobile's
 * deriveContextLine.
 */
export function deriveContextLine(player: MatchupStarter): string | null {
  const why = (player.why ?? "").trim();
  if (!why) return null;
  let parts = why.split(" · ").map((part) => part.trim()).filter(Boolean);
  if (parts.length && /\btier$/i.test(parts[0])) {
    parts = parts.slice(1);
  }
  const opportunity = (player.opportunity_label ?? "").trim().toLowerCase();
  if (parts.length && opportunity && parts[0].toLowerCase() === opportunity) {
    parts = parts.slice(1);
  }
  parts = parts.filter((part) => !part.includes(" — "));
  if (parts.length === 0) return null;
  const phrase = parts.join(" · ");
  return phrase.charAt(0).toUpperCase() + phrase.slice(1);
}

// ---------------------------------------------------------------------------
// Matchup page layout (owner's concept, 2026-10-21): scoreboard, insights,
// lineup comparison (Suggested | Actual), suggested moves. Pure helpers only;
// every number comes from GET .../matchup.
// ---------------------------------------------------------------------------

/** Signed one-decimal number: "+12.4", "-8.2", "0.0". */
export function formatSigned(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "0.0";
  return `${rounded > 0 ? "+" : "-"}${Math.abs(rounded).toFixed(1)}`;
}

/** Compact lineup-slot label for the narrow middle column and move badges. */
export function slotDisplayLabel(slot: string | null | undefined): string {
  const label = (slot ?? "").toUpperCase();
  if (label === "SUPER_FLEX") return "SF";
  if (label === "WR/RB") return "W/R";
  if (label === "REC_FLEX") return "W/T";
  if (label === "IDP_FLEX") return "IDP";
  return label || "—";
}

/** True once any starter's own game has kicked off (Sleeper scores are
 * real from then on). Pre-game, a real 0.0 isn't a score yet. */
export function hasKickedOff(matchup: MatchupResponse): boolean {
  return matchup.game_state === "live" || matchup.game_state === "between_games" || matchup.game_state === "final";
}

export type LineupPlayer = MatchupStarter | MatchupRealStarter;

/** One player's number for the lineup table: his real points once his own
 * game has started, this week's projection before that. Mirrors
 * modules.matchup_win_probability.starter_expected_points, so the table,
 * the edges and the win probability agree. */
export function lineupPlayerPoints(player: LineupPlayer): {
  value: number | null;
  kind: "pts" | "proj" | null;
  note: "bye" | null;
} {
  const actual = player.actual_points ?? null;
  if (player.game_started === true && actual != null) return { value: actual, kind: "pts", note: null };
  const projection = player.projection;
  if (projection?.status === "ok" && projection.point_estimate != null) {
    return { value: projection.point_estimate, kind: "proj", note: null };
  }
  if (projection?.status === "bye_week") return { value: null, kind: null, note: "bye" };
  return { value: null, kind: null, note: null };
}

export interface LineupComparisonRow {
  slot: string;
  mine: LineupPlayer | "empty" | null;
  opponent: LineupPlayer | "empty" | null;
}

/**
 * Side-by-side rows by lineup slot. Each side's players are grouped by slot
 * and zipped within the group (both teams share the league's slot list), in
 * order of first appearance — Sleeper's roster_positions order on the
 * Actual tab, the suggested lineup's slot order on the Suggested tab.
 * Empty Sleeper slots render as "empty"; a slot only one side fills (a
 * missing DEF, say) leaves the other cell null.
 */
export function lineupComparisonRows(
  mine: LineupPlayer[],
  opponent: LineupPlayer[],
  myEmptySlots: string[] = [],
  opponentEmptySlots: string[] = [],
): LineupComparisonRow[] {
  const order: string[] = [];
  const groups = new Map<string, { mine: (LineupPlayer | "empty")[]; opponent: (LineupPlayer | "empty")[] }>();
  const group = (slot: string) => {
    if (!groups.has(slot)) {
      groups.set(slot, { mine: [], opponent: [] });
      order.push(slot);
    }
    return groups.get(slot)!;
  };
  for (const player of mine) group(player.slot || "—").mine.push(player);
  for (const slot of myEmptySlots) group(slot).mine.push("empty");
  for (const player of opponent) group(player.slot || "—").opponent.push(player);
  for (const slot of opponentEmptySlots) group(slot).opponent.push("empty");

  const rows: LineupComparisonRow[] = [];
  for (const slot of order) {
    const { mine: mySlot, opponent: theirSlot } = groups.get(slot)!;
    const count = Math.max(mySlot.length, theirSlot.length);
    for (let index = 0; index < count; index += 1) {
      rows.push({ slot, mine: mySlot[index] ?? null, opponent: theirSlot[index] ?? null });
    }
  }
  return rows;
}

/** Plain-English position group: "WRs" for a multi-starter room, "QB" for one. */
function positionGroupName(edge: MatchupPositionEdge): string {
  return edge.my_count > 1 ? `${edge.position}s` : edge.position;
}

function joinWithAnd(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** A position needs at least this many points either way to be called an
 * edge or a problem; anything inside it is "level". */
export const POSITION_EDGE_THRESHOLD = 1;

/**
 * The insight sentence under the verdict, built only from the real
 * per-position numbers (multi-factor rule: no canned copy). Names up to two
 * strongest edges for you and two for your opponent, with their numbers.
 * Null when there are no edges to explain.
 */
export function edgeExplanation(edges: MatchupPositionEdge[] | null | undefined): string | null {
  if (!edges || edges.length === 0) return null;
  const strengths = edges.filter((edge) => edge.edge >= POSITION_EDGE_THRESHOLD).slice(0, 2);
  const weaknesses = edges
    .filter((edge) => edge.edge <= -POSITION_EDGE_THRESHOLD)
    .sort((a, b) => a.edge - b.edge)
    .slice(0, 2);
  const describe = (edge: MatchupPositionEdge) => `${positionGroupName(edge)} (${formatSigned(edge.edge)})`;
  const verb = strengths.length === 1 && strengths[0].my_count <= 1 ? "gives" : "give";

  if (strengths.length && weaknesses.length) {
    return `Your ${joinWithAnd(strengths.map(describe))} ${verb} you an edge, but your ${joinWithAnd(
      weaknesses.map(describe),
    )} could be a problem.`;
  }
  if (strengths.length) {
    return `Your ${joinWithAnd(strengths.map(describe))} ${verb} you an edge, and no position trails by more than a point.`;
  }
  if (weaknesses.length) {
    return `Your opponent is stronger at ${joinWithAnd(
      weaknesses.map(describe),
    )}, and no position gives you more than a point.`;
  }
  return "Every position is within a point either way.";
}

export type VerdictTone = "positive" | "risk" | "neutral";

/** Win probability at or beyond this distance from 50% counts as "favored". */
export const FAVORED_MARGIN = 0.05;

/**
 * The one-line verdict at the top of Matchup Insights. Final weeks read
 * the real result; otherwise it's the live win probability (which already
 * folds in real points for games that have started). Honest when there's
 * no probability: says so rather than guessing.
 */
export function matchupVerdict(matchup: MatchupResponse): { headline: string; tone: VerdictTone } {
  const real = matchup.real_comparison;
  if (matchup.game_state === "final" && real) {
    if (real.edge === "you") return { headline: "You won this week.", tone: "positive" };
    if (real.edge === "opponent") return { headline: "You lost this week.", tone: "risk" };
    return { headline: "This week ended in a tie.", tone: "neutral" };
  }
  const odds = matchup.win_probability;
  if (odds?.available && odds.probability != null) {
    const live = matchup.game_state === "live" || matchup.game_state === "between_games";
    if (odds.probability >= 0.5 + FAVORED_MARGIN) {
      return { headline: live ? "You're on track to win." : "You're favored to win.", tone: "positive" };
    }
    if (odds.probability <= 0.5 - FAVORED_MARGIN) {
      return { headline: live ? "Your opponent is on track to win." : "Your opponent is favored.", tone: "risk" };
    }
    return { headline: "Too close to call.", tone: "neutral" };
  }
  return { headline: "Not enough projections yet to call it.", tone: "neutral" };
}

/** Why the win probability is missing, in plain words. */
export function winProbabilityUnavailableMessage(matchup: MatchupResponse): string {
  if (matchup.win_probability?.reason === "insufficient_coverage") {
    return "Win probability needs projections for more of each lineup.";
  }
  return "Win probability appears once Sleeper posts both lineups.";
}

/** "RB2" for the second RB slot in a lineup with several, "FLEX" for the
 * only one. Ordinals follow the actual Sleeper lineup's own slot order. */
export function moveSlotLabel(move: MatchupSuggestedMove, actualStarters: MatchupRealStarter[]): string {
  const base = slotDisplayLabel(move.slot);
  const sameSlot = actualStarters.filter((player) => player.slot === move.slot);
  if (sameSlot.length <= 1 || !move.over) return base;
  const index = sameSlot.findIndex((player) => player.player_id === move.over!.player_id);
  return index >= 0 ? `${base}${index + 1}` : base;
}

/** The "Over ..." line under a suggested move. */
export function moveOverLine(move: MatchupSuggestedMove): string {
  if (!move.over) return `Fills your empty ${slotDisplayLabel(move.slot)} slot`;
  const name = move.over.name || "Unknown player";
  if (move.over_reason === "bye_week") return `Over ${name} (on bye)`;
  if (move.over_reason === "ruled_out") return `Over ${name} (${move.over.injury_label || "ruled out"})`;
  return `Over ${name} (${move.over.points != null ? `Proj ${move.over.points.toFixed(1)}` : "no projection"})`;
}

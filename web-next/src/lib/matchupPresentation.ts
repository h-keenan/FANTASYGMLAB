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
import type { MatchupRealStarter, MatchupSide, MatchupStarter, PlayerWeekProjection } from "./api";

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
    linkAccount: "Link your Sleeper account and join this league from Home to see this week's matchup.",
  });
  return shared ?? DEFAULT_MATCHUP_MESSAGE;
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

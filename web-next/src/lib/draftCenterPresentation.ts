import type { DraftPickAsset } from "@/lib/api";

/**
 * Pure presentation helpers for Draft Center (Revision 14) — ports the
 * exact pick-scoping/grouping logic mobile's DraftCenterScreen.tsx computes
 * inline in its own useMemo hooks, as standalone functions so they're
 * testable without rendering a component or running a dev server.
 *
 * Posture/decision/partner-card TONE colors deliberately do NOT get a new
 * tone->color map here: those cards use the exact same `tone-${tone}` /
 * `.tone-value` CSS utility classes (globals.css, originally
 * modules/card_hierarchy_styles.py) MyTeamContent.tsx's Strength & Pressure
 * and Position Groups cards already use, since draft_center_ui.py's tone
 * vocabulary (power/strength/opportunity/strategy/weakness/risk/franchise)
 * is that same vocabulary, not a different taxonomy needing its own map.
 */

export const POSTURE_REASON_MESSAGE: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper account and join this league from Home to see your own draft posture.",
  sleeper_user_not_found: "We couldn't find your linked Sleeper account in this league.",
  not_a_member_of_league: "You don't appear to have a roster in this league.",
  no_draft_capital_row: "Your roster's draft-capital data isn't available yet.",
};

export type PickScope = "mine" | "league";

/** Scope (My Picks vs League) then sort — season asc, round asc, score
 * desc — same precedence mobile's DraftCenterScreen.tsx `visiblePicks`
 * useMemo uses. Scoping to "mine" with no resolved roster id falls back to
 * every pick, same as mobile (there's nothing to scope to). */
export function visibleDraftPicks(
  picks: DraftPickAsset[],
  scope: PickScope,
  myRosterId: string,
): DraftPickAsset[] {
  const scoped =
    scope === "mine" && myRosterId ? picks.filter((pick) => pick.owner_roster_id === myRosterId) : picks;
  return [...scoped].sort(
    (a, b) =>
      (a.season ?? 0) - (b.season ?? 0) ||
      (a.round ?? 0) - (b.round ?? 0) ||
      (b.score ?? 0) - (a.score ?? 0),
  );
}

/** Groups already-sorted picks by season, seasons ascending — same shape
 * as mobile's `pickSeasons` useMemo. Call with the output of
 * `visibleDraftPicks` so within-season order matches. */
export function groupPicksBySeason(picks: DraftPickAsset[]): [number, DraftPickAsset[]][] {
  const bySeason = new Map<number, DraftPickAsset[]>();
  for (const pick of picks) {
    const season = pick.season ?? 0;
    const bucket = bySeason.get(season);
    if (bucket) bucket.push(pick);
    else bySeason.set(season, [pick]);
  }
  return [...bySeason.entries()].sort(([a], [b]) => a - b);
}

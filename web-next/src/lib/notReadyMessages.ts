/**
 * Shared "not ready yet" classification for the GET endpoints that return a
 * `reason` instead of data (services/mobile_api_service.py's
 * `_resolve_my_roster` and friends: no linked Sleeper username, that
 * username isn't a member of the league, or the roster resolved but is
 * empty). My Team, Trade Hub, and now Waivers each hit the exact same three
 * `reason` values — this was a byte-identical `NO_LEAGUE_REASONS` Set plus a
 * near-identical if/elif ladder duplicated three times
 * (myTeamPresentation.ts, tradeHubPresentation.ts, and this page's own
 * waiversPresentation.ts). Consolidated here (Revision 4 CSS/redundancy
 * cleanup pass) so only the page-specific copy for each reason still lives
 * at each call site.
 */
const LEAGUE_LINK_REASONS = new Set([
  "no_sleeper_username_linked",
  "sleeper_user_not_found",
  "not_a_member_of_league",
]);

export function notReadyReasonMessage(
  reason: string,
  copy: { linkAccount: string; emptyRoster?: string },
): string | null {
  if (LEAGUE_LINK_REASONS.has(reason)) return copy.linkAccount;
  if (reason === "empty_roster" && copy.emptyRoster) return copy.emptyRoster;
  if (reason === "no_player_data") {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

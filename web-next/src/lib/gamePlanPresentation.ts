/** destination -> this app's own internal Next.js route path, for every
 * destination that now has a real page (app/trade-hub/[leagueId],
 * app/waivers/[leagueId] as of Revision 4, app/gm-plan/[leagueId] as of
 * Revision 9) instead of Streamlit's `?page=` router. Every other
 * destination is still Streamlit-only. "gm_plan" isn't actually emitted
 * by modules.daily_gm_briefing's `_tile_destination` today (checked: it
 * only ever returns waivers/my_team/trade_hub/dashboard, or an explicit
 * tile route_key — no caller sets that to "gm_plan" yet), but is listed
 * here ahead of time the same way "rankings" already was, so a future
 * tile pointed at GM Plan routes internally without a second edit here.
 * "gm_targets" (Revision 11) is listed the same way, ahead of any tile
 * actually emitting it. "trade_analyzer" (Revision 15) is too — Today's
 * Game Plan doesn't emit it today either, same as "gm_plan"/"gm_targets"
 * above. "players" (Revision 16) is the same again — modules.
 * daily_gm_briefing's `_tile_destination` doesn't emit it, but Players now
 * has a real page too (app/players/[leagueId]). "trade_finder" (Revision 17)
 * is the same once more — Trade Finder now has a real page
 * (app/trade-finder/[leagueId]) too.
 *
 * Shared between GamePlanCard (Top Priority's own card) and WatchListCard
 * (every other Today's Game Plan item, grouped into one card) — pulled out
 * of GamePlanCard.tsx rather than duplicated. */
export const GAME_PLAN_INTERNAL_ROUTES: Record<string, string> = {
  trade_hub: "trade-hub",
  waivers: "waivers",
  rankings: "league-rankings",
  gm_plan: "gm-plan",
  gm_targets: "gm-targets",
  trade_analyzer: "trade-analyzer",
  players: "players",
  trade_finder: "trade-finder",
};

/** Backend categories are snake_case tokens (e.g. "top_priority") — title-case
 * them for display, matching Streamlit's kicker labels (Top Priority / Watch /
 * Waiver Opportunity / League Movement). */
export function formatGamePlanCategory(category: string): string {
  return category
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

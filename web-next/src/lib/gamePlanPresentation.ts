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
  // "my_team" and "dashboard" (2026-10-18, classic-domain audit,
  // coridian_: "we need to remove the classic domain entirely from being
  // accessible from the main site") — `_tile_destination`'s two most
  // common real values, and both already have real pages here
  // (app/my-team/[leagueId], app/dashboard/[leagueId]); there was never a
  // reason for Today's Game Plan to still deep-link out to Streamlit for
  // either one.
  my_team: "my-team",
  dashboard: "dashboard",
  rankings: "league-rankings",
  gm_plan: "gm-plan",
  gm_targets: "gm-targets",
  trade_analyzer: "trade-analyzer",
  players: "players",
  trade_finder: "trade-finder",
  // Strategy Check (modules.dashboard_engine.build_strategy_check_tile,
  // 2026-10-18) routes here to update the declared stance it compared
  // against. Team Situation already has a real page.
  team_situation: "team-situation",
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

/** Recommendation-compliance audit, Check 3 — CTA reachability (2026-10-19):
 * a tile's CTA used to link to the generic per-league landing page for its
 * destination even when the tile is clearly about one specific player (e.g.
 * "add this waiver player" / "consider this trade"), so the user had to
 * manually re-find the exact thing the card just told them about. Every
 * BriefingItem already carries `route_player_id` for that one unambiguous
 * player (modules.dashboard_engine's build_waiver_tile/build_trade_tile/
 * build_injury_tile/build_value_trend_tile) — this resolves which id to
 * send, falling back to the trade package's own headline receive-side
 * player for a trade tile that (per BriefingItemPlayers' same precedent)
 * sometimes arrives with trade_package populated but route_player_id empty. */
export function resolveGamePlanTargetPlayerId(item: {
  route_player_id: string;
  presentation?: { trade_package?: { receive: Array<{ player_id?: string }> } } | null;
}): string {
  if (item.route_player_id) return item.route_player_id;
  const receive = item.presentation?.trade_package?.receive || [];
  const headlinePlayer = receive.find((asset) => Boolean(asset.player_id));
  return headlinePlayer?.player_id || "";
}

/** Builds the Link href for a Game Plan tile's CTA to one of this app's own
 * internal routes (see GAME_PLAN_INTERNAL_ROUTES above). Appends `playerId`
 * when a specific recommendation player is known so Waivers/Trade Hub (the
 * only two destinations that currently read it — see those pages) can
 * deep-link straight to it instead of their generic landing view. Every
 * other destination simply ignores the extra query param if present —
 * same fail-open principle as the rest of this app: a stale/absent id never
 * breaks the page, it just means no highlight. */
export function gamePlanTileHref(internalRoute: string, leagueId: string, leagueName: string, targetPlayerId: string): string {
  const params = new URLSearchParams({ name: leagueName });
  if (targetPlayerId) {
    params.set("playerId", targetPlayerId);
  }
  return `/${internalRoute}/${encodeURIComponent(leagueId)}?${params.toString()}`;
}

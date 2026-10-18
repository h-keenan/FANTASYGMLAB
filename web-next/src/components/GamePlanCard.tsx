import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { destinationCtaLabel, streamlitPageUrl } from "@/lib/streamlitLink";

/**
 * Ports modules/daily_gm_briefing_ui.py's Today's Game Plan card: kicker
 * (category), headline, reason, an explicit "Open X" CTA. The visible
 * "Open" button is a real <Link> here instead of app.py's `[data-route]`
 * div-click-delegation hack (see Dashboard research notes) — normal React
 * navigation is simpler and was explicitly called out as the reason to do
 * this natively rather than port the mechanism.
 */
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
 * (app/trade-finder/[leagueId]) too. */
const INTERNAL_ROUTES: Record<string, string> = {
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
function formatCategory(category: string): string {
  return category
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function GamePlanCard({
  item,
  leagueId,
  leagueName,
}: {
  item: BriefingItem;
  /** Trade Hub now has a real Next.js page (see app/trade-hub/[leagueId]) —
   * a card whose destination is "trade_hub" links there internally instead
   * of Streamlit's `?page=` router. Every other destination is still
   * Streamlit-only for this revision. */
  leagueId: string;
  leagueName: string;
}) {
  const internalRoute = INTERNAL_ROUTES[item.destination];
  return (
    <article
      className="flex flex-col gap-2 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <span
        className="uppercase"
        style={{
          font: "var(--type-badge-size)",
          letterSpacing: "var(--letter-spacing-badge)",
          color: "var(--color-accent)",
        }}
      >
        {formatCategory(item.category)}
      </span>
      <h3 style={{ font: "var(--font-card-title)" }}>{item.headline}</h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {item.reason}
      </p>
      {/* coridian_, 2026-10-18: "Top priority still has no player card" /
          "These player cards are too small" — Top Trade Opportunity's tile
          (modules.dashboard_engine.build_trade_tile) always carries a real
          give/get package under presentation.trade_package even when the
          single route_player_* fields below don't resolve for it (a 2-sided
          trade isn't one player). Reusing ExchangeSide here is the same
          component Trade Hub/GM Plan/Trade History already render it with
          — same 40px avatars, same OVR gauge, not a smaller one-off. */}
      {item.presentation?.trade_package &&
      (item.presentation.trade_package.send.length > 0 || item.presentation.trade_package.receive.length > 0) ? (
        <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-2 items-start">
          <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={item.presentation.trade_package.send} />
          <div
            className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
            style={{ color: "var(--color-accent)" }}
            aria-hidden="true"
          >
            FOR
          </div>
          <ExchangeSide label="You get" dotColor="var(--color-success)" assets={item.presentation.trade_package.receive} />
        </div>
      ) : item.route_player_name && item.route_player_id ? (
        <PlayerIdentityTrigger
          identity={{
            player_id: item.route_player_id,
            name: item.route_player_name,
            position: item.route_player_position,
            team: item.route_player_team,
            tier: item.route_player_tier,
            score: item.route_player_score,
            sourceLabel: "GM Plan",
          }}
          className="flex items-center gap-2 text-xs"
        >
          <span style={{ color: "var(--color-text-muted)" }}>
            <PositionBadge position={item.route_player_position} />
          </span>
          <PlayerAvatar playerId={item.route_player_id} tier={item.route_player_tier} size={32} />
          <span style={{ color: "var(--color-text-muted)" }}>{item.route_player_name}</span>
          {item.route_player_team ? <span style={{ color: "var(--color-text-muted)" }}>· {item.route_player_team}</span> : null}
        </PlayerIdentityTrigger>
      ) : null}
      {item.mentioned_players && item.mentioned_players.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          {item.mentioned_players
            .filter((player) => player.player_id !== item.route_player_id)
            .map((player) => (
              <PlayerIdentityTrigger
                key={player.player_id}
                identity={{
                  player_id: player.player_id,
                  name: player.name,
                  position: player.position,
                  team: player.team,
                  tier: player.player_tier,
                  score: null,
                  sourceLabel: "GM Plan",
                }}
                className="flex items-center gap-2 text-xs"
              >
                <span style={{ color: "var(--color-text-muted)" }}>
                  <PositionBadge position={player.position} />
                </span>
                <PlayerAvatar playerId={player.player_id} tier={player.player_tier} size={32} />
                <span style={{ color: "var(--color-text-muted)" }}>{player.name}</span>
                {player.team ? <span style={{ color: "var(--color-text-muted)" }}>· {player.team}</span> : null}
              </PlayerIdentityTrigger>
            ))}
        </div>
      ) : null}
      {internalRoute ? (
        <Link
          href={`/${internalRoute}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
          className="self-start text-sm font-bold mt-1"
          style={{ color: "var(--color-accent)" }}
        >
          {destinationCtaLabel(item.destination)} →
        </Link>
      ) : (
        <a
          href={streamlitPageUrl(item.destination)}
          className="self-start text-sm font-bold mt-1"
          style={{ color: "var(--color-accent)" }}
        >
          {destinationCtaLabel(item.destination)} →
        </a>
      )}
    </article>
  );
}

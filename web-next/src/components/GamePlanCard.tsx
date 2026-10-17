import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
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
      {item.route_player_name && item.route_player_id ? (
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
          <PlayerAvatar playerId={item.route_player_id} tier={item.route_player_tier} size={24} />
          <span style={{ color: "var(--color-text-muted)" }}>{item.route_player_name}</span>
          {item.route_player_team ? <span style={{ color: "var(--color-text-muted)" }}>· {item.route_player_team}</span> : null}
        </PlayerIdentityTrigger>
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

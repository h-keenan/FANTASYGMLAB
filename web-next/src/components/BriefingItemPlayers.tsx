import type { BriefingItem } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";

/**
 * The compact player-card visual for a BriefingItem — give/get trade
 * package, a single route player, or a list of mentioned players.
 * Extracted out of GamePlanCard (Today's Game Plan) so Portfolio's
 * per-league signal rows can render the exact same identity chips instead
 * of the pipe-separated plain text they used before (coridian_, 2026-10-18,
 * screenshot: "this portfolio looks terrible, with zero player PFPs. These
 * need to have the compact player cards that we were supposed to make" —
 * the compact cards already existed here, just weren't reused for
 * Portfolio's own signal rows).
 */
export function BriefingItemPlayers({ item, sourceLabel }: { item: BriefingItem; sourceLabel: string }) {
  if (
    item.presentation?.trade_package &&
    (item.presentation.trade_package.send.length > 0 || item.presentation.trade_package.receive.length > 0)
  ) {
    return (
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
    );
  }

  // route_player_* (the one unambiguous player to deep-link a whole-card
  // tap to) and mentioned_players (every player the text actually names,
  // up to 3) are complementary, not mutually exclusive — a "1 injured
  // starter" Watch card routes to that one starter AND names 2 other
  // future-asset players in its reason text. Rendering these as an
  // if/else-if (as a prior version of this component briefly did) silently
  // dropped every mentioned player except the route target whenever a
  // route_player happened to resolve (coridian_, 2026-10-18, screenshot:
  // "it lists starters but it only shows one player's compact player
  // card"). Both render; mentioned_players is filtered to skip whichever
  // one route_player already showed, so nobody appears twice.
  const hasRoutePlayer = Boolean(item.route_player_name && item.route_player_id);
  const otherMentionedPlayers = (item.mentioned_players || []).filter(
    (player) => player.player_id !== item.route_player_id,
  );

  if (!hasRoutePlayer && otherMentionedPlayers.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {hasRoutePlayer ? (
        <PlayerIdentityTrigger
          identity={{
            player_id: item.route_player_id,
            name: item.route_player_name,
            position: item.route_player_position,
            team: item.route_player_team,
            tier: item.route_player_tier,
            score: item.route_player_score,
            sourceLabel,
          }}
          className="flex items-center gap-2 text-xs"
        >
          <span style={{ color: "var(--color-text-muted)" }}>
            <PositionBadge position={item.route_player_position} />
          </span>
          <PlayerAvatar playerId={item.route_player_id} tier={item.route_player_tier} size={32} />
          <span style={{ color: "var(--color-text-muted)" }}>{item.route_player_name}</span>
          <PlayerInjuryBadge status={item.route_player_injury_status} />
          {item.route_player_team ? <span style={{ color: "var(--color-text-muted)" }}>· {item.route_player_team}</span> : null}
        </PlayerIdentityTrigger>
      ) : null}
      {otherMentionedPlayers.map((player) => (
        <PlayerIdentityTrigger
          key={player.player_id}
          identity={{
            player_id: player.player_id,
            name: player.name,
            position: player.position,
            team: player.team,
            tier: player.player_tier,
            score: null,
            sourceLabel,
          }}
          className="flex items-center gap-2 text-xs"
        >
          <span style={{ color: "var(--color-text-muted)" }}>
            <PositionBadge position={player.position} />
          </span>
          <PlayerAvatar playerId={player.player_id} tier={player.player_tier} size={32} />
          <span style={{ color: "var(--color-text-muted)" }}>{player.name}</span>
          <PlayerInjuryBadge status={player.injury_status} />
          {player.team ? <span style={{ color: "var(--color-text-muted)" }}>· {player.team}</span> : null}
        </PlayerIdentityTrigger>
      ))}
    </div>
  );
}

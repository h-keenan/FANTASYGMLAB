"use client";

import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { byeCover, watchSummary, watchTag, watchTitle } from "@/lib/dashboardPresentation";
import {
  GAME_PLAN_INTERNAL_ROUTES,
  gamePlanTileHref,
  resolveGamePlanTargetPlayerId,
} from "@/lib/gamePlanPresentation";
import { destinationCtaLabel } from "@/lib/destinationLabels";
import { PlayerName } from "@/components/PlayerName";

/**
 * Watchlist & Alerts: every Game Plan item except Top Priority, as one
 * list. Each row is one tap target: a type tag (TRENDING / INJURY / WAIVER / BYE),
 * the player (avatar, name, position/team chip), one clean sentence of why
 * (lib/dashboardPresentation.ts watchSummary: built from structured fields,
 * else the feed's first sentence; clamped to two lines) and a chevron. A row with no player drops the avatar slot and shows its headline as title.
 */
export function WatchListCard({
  items,
  leagueId,
  leagueName,
}: {
  items: BriefingItem[];
  leagueId: string;
  leagueName: string;
}) {
  if (items.length === 0) return null;
  return (
    <article className="glass-surface flex flex-col" style={{ overflow: "hidden" }} data-testid="watchlist-alerts">
      {items.map((item, index) => {
        const internalRoute = GAME_PLAN_INTERNAL_ROUTES[item.destination] ?? "dashboard";
        const tag = watchTag(item);
        const mentioned = item.mentioned_players?.[0];
        const playerId = item.route_player_id || mentioned?.player_id || "";
        const name = item.route_player_name || mentioned?.name || "";
        const position = item.route_player_position || mentioned?.position || "";
        const team = item.route_player_team || mentioned?.team || "";
        const tier = item.route_player_tier || mentioned?.player_tier || "";
        const injury = item.route_player_injury_status || mentioned?.injury_status || "";
        const bye = byeCover(item);
        const label = `${destinationCtaLabel(item.destination)}: ${item.headline}`;
        const rowStyle = index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined;
        const body = (
          <>
            {playerId ? (
              <PlayerAvatar playerId={playerId} tier={tier} size={36} />
            ) : null}
            <span className="flex flex-col items-start gap-1 min-w-0 flex-1">
              <ToneBadge label={tag.label} color={tag.color} />
              <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 min-w-0">
                {name ? (
                  <PlayerName name={name} className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
                ) : (
                  <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
                    {watchTitle(item)}
                  </span>
                )}
                {name ? <PositionBadge position={position} /> : null}
                {name && team ? (
                  <span className="text-xs shrink-0" style={{ color: "var(--color-text-muted)" }}>
                    {team}
                  </span>
                ) : null}
                <PlayerInjuryBadge status={injury} />
              </span>
              <span
                className="text-xs min-w-0 self-stretch"
                style={{
                  color: "var(--color-text-secondary)",
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical" as const,
                  overflow: "hidden",
                }}
              >
                {watchSummary(item)}
              </span>
              {bye && bye.suggestions.length > 0 ? (
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="bye-cover-fillins">
                  {bye.suggestions.map((fa) => (
                    <span key={fa.player_id} className="flex items-center gap-1.5 min-w-0">
                      <PlayerAvatar playerId={fa.player_id} tier={fa.player_tier} size={24} />
                      <span className="text-xs font-semibold" style={{ color: "var(--color-text-primary)" }}>
                        {fa.name}
                      </span>
                      <PositionBadge position={fa.position} />
                    </span>
                  ))}
                </span>
              ) : null}
            </span>
          </>
        );
        const className = "flex items-center gap-3 px-3 py-2.5";
        const key = item.recommendation_id || item.headline;
        return (
          <Link
            key={key}
            href={gamePlanTileHref(
              internalRoute,
              leagueId,
              leagueName,
              // Waivers highlights the player it is given: for a bye alert that is the best fill-in, not the rostered starter.
              bye ? (bye.suggestions[0]?.player_id ?? "") : resolveGamePlanTargetPlayerId(item),
            )}
            aria-label={label}
            className={className}
            style={rowStyle}
          >
            {body}
          </Link>
        );
      })}
    </article>
  );
}

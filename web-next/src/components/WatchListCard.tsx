"use client";

import Link from "next/link";

import type { BriefingItem } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { usageTrendPct, watchTag } from "@/lib/dashboardPresentation";
import {
  GAME_PLAN_INTERNAL_ROUTES,
  gamePlanTileHref,
  resolveGamePlanTargetPlayerId,
} from "@/lib/gamePlanPresentation";
import { destinationCtaLabel } from "@/lib/destinationLabels";

/**
 * Watchlist & Alerts: every Game Plan item except Top Priority, as one
 * list. Each row is one tap target: a type tag (TRENDING / INJURY / WAIVER),
 * the player, one line of why, and on the right a trend indicator only when
 * the item carries a real figure (today: the usage-drop percentage of a
 * Value Trend item). Rows without data show just the chevron; nothing is
 * drawn or labelled as a placeholder. Beginner mode shows the full reason,
 * advanced clamps it to one line.
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
  const copy = useExperienceCopy();
  if (items.length === 0) return null;
  return (
    <article className="glass-surface flex flex-col" style={{ overflow: "hidden" }} data-testid="watchlist-alerts">
      {items.map((item, index) => {
        const internalRoute = GAME_PLAN_INTERNAL_ROUTES[item.destination] ?? "dashboard";
        const tag = watchTag(item);
        const trendPct = usageTrendPct(item);
        const mentioned = item.mentioned_players?.[0];
        const playerId = item.route_player_id || mentioned?.player_id || "";
        const name = item.route_player_name || mentioned?.name || "";
        const position = item.route_player_position || mentioned?.position || "";
        const team = item.route_player_team || mentioned?.team || "";
        const tier = item.route_player_tier || mentioned?.player_tier || "";
        const injury = item.route_player_injury_status || mentioned?.injury_status || "";
        const label = `${destinationCtaLabel(item.destination)}: ${item.headline}`;
        const rowStyle = index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined;
        const body = (
          <>
            <span className="shrink-0 w-[4.25rem]">
              <ToneBadge label={tag.label} color={tag.color} />
            </span>
            {playerId ? <PlayerAvatar playerId={playerId} tier={tier} size={36} /> : null}
            <span className="flex flex-col gap-0.5 min-w-0 flex-1">
              <span className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
                  {name || item.headline}
                </span>
                {team ? (
                  <span className="hidden sm:inline text-xs shrink-0" style={{ color: "var(--color-text-muted)" }}>
                    {team}
                  </span>
                ) : null}
                <PlayerInjuryBadge status={injury} />
              </span>
              <span className="flex items-start gap-1.5 min-w-0">
              <PositionBadge position={position} />
              <span
                className="text-xs min-w-0"
                style={{
                  color: "var(--color-text-secondary)",
                  ...(copy.isBeginner
                    ? {}
                    : { display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical" as const, overflow: "hidden" }),
                }}
              >
                {item.reason}
              </span>
              </span>
            </span>
            {trendPct !== null ? (
              <span className="shrink-0">
                <ToneBadge label={`↓ ${trendPct}%`} color="var(--color-danger)" />
              </span>
            ) : null}
            <span aria-hidden="true" className="shrink-0 text-lg" style={{ color: "var(--color-accent)" }}>
              ›
            </span>
          </>
        );
        const className = "flex items-center gap-3 px-3 py-2.5";
        const key = item.recommendation_id || item.headline;
        return (
          <Link
            key={key}
            href={gamePlanTileHref(internalRoute, leagueId, leagueName, resolveGamePlanTargetPlayerId(item))}
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

"use client";

import { useEffect, useState } from "react";

import { api, type WeeklyStatPoint } from "@/lib/api";
import { CHART_HEIGHT, WeeklyPointsPanel } from "@/components/WeeklyPointsChart";

/**
 * Points By Week, with a season-back selector — ports mobile's
 * PlayerDetailScreen TrendsSection (mobile/src/screens/PlayerDetailScreen.tsx,
 * ~line 633). Extracted from PlayerQuickView.tsx's own inline "Week by
 * Week" section (the modal still renders this exact panel) so the full
 * Player Profile page's Trends tab (players/[leagueId]/[playerId]) can reuse
 * the identical fetch/selector logic instead of a second copy — see that
 * page's own module doc comment and PlayerQuickView.tsx's header doc
 * comment on the "PQV parity gap" this closes.
 *
 * `null` selectedSeason = backend default (the current season). The real
 * current season is learned from the backend's own default-season response
 * rather than guessed client-side (`currentSeasonAnchor`), so the "how far
 * back can I go" selector stays anchored even after the user has picked an
 * older season.
 */
export function PlayerTrendsPanel({
  playerId,
  name,
  gradientId = "player-trends-fill",
}: {
  playerId: string;
  name: string;
  /** Unique per panel on the page — see WeeklyPointsPanel's own docstring
   * for why two panels can't share one gradient id. */
  gradientId?: string;
}) {
  const [weeklyStats, setWeeklyStats] = useState<{ season: number; weeks: WeeklyStatPoint[] } | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [currentSeasonAnchor, setCurrentSeasonAnchor] = useState<number | null>(null);
  const [loadError, setLoadError] = useState(false);

  // No setState synchronously at the top of this effect (React's
  // react-hooks/set-state-in-effect rule flags that pattern, same reasoning
  // PlayerCompareContent.tsx's own modelsLoadedFor comment documents) — the
  // render below derives "still loading" from weeklyStats being null rather
  // than a separately-reset loading flag.
  useEffect(() => {
    let cancelled = false;

    api
      .getPlayerWeeklyStats(playerId, selectedSeason ?? undefined)
      .then((response) => {
        if (cancelled) return;
        setWeeklyStats({ season: response.season, weeks: response.weeks });
        setLoadError(false);
        if (selectedSeason == null) setCurrentSeasonAnchor(response.season);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [playerId, selectedSeason]);

  // mobile_api_service.py's own bound: MAX_WEEKLY_STATS_SEASONS_BACK = 7.
  const WEEKLY_STATS_SEASONS_BACK = 7;
  const seasonOptions = currentSeasonAnchor
    ? Array.from({ length: WEEKLY_STATS_SEASONS_BACK + 1 }, (_, i) => currentSeasonAnchor - i)
    : [];

  if (!weeklyStats && loadError) {
    return (
      <p className="pqv-status-text" role="alert">
        Couldn&apos;t load this player&apos;s weekly trends right now.
      </p>
    );
  }
  if (!weeklyStats) {
    // Skeleton sized to the real section below (name label, CHART_HEIGHT
    // chart, caption line) so this panel's own independent fetch doesn't
    // grow the modal a second time once the outer loading gate has
    // already resolved — see globals.css's .pqv-skeleton-chart comment.
    return (
      <section className="pqv-stat-season" aria-busy="true">
        <div className="pqv-skeleton-line pqv-skeleton-line--label" />
        <div className="pqv-skeleton-chart" style={{ height: CHART_HEIGHT }} />
        <div className="pqv-skeleton-line pqv-skeleton-line--short" style={{ alignSelf: "center" }} />
        <p className="sr-only" role="status">
          Loading weekly trends…
        </p>
      </section>
    );
  }

  return (
    <section className="pqv-stat-season">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3>Week by Week · {weeklyStats.season}</h3>
        {seasonOptions.length > 1 ? (
          <select
            aria-label="Season"
            value={selectedSeason ?? currentSeasonAnchor ?? ""}
            onChange={(event) => setSelectedSeason(Number(event.target.value))}
            className="text-xs px-2 py-1"
            style={{
              background: "var(--color-surface-muted)",
              color: "var(--color-text-secondary)",
              border: "var(--border-width-default) solid var(--color-border)",
            }}
          >
            {seasonOptions.map((season) => (
              <option key={season} value={season}>
                {season}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <WeeklyPointsPanel name={name} weeks={weeklyStats.weeks} season={weeklyStats.season} gradientId={gradientId} />
    </section>
  );
}

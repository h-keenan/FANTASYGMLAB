"use client";

import { useEffect, useState } from "react";

import { api, type CareerSeason } from "@/lib/api";

/**
 * Career tab (ports mobile's PlayerDetailScreen CareerSection,
 * mobile/src/screens/PlayerDetailScreen.tsx ~line 765) for the full Player
 * Profile page — the "PQV parity gap" (see PlayerQuickView.tsx's own header
 * doc comment and docs/roadmap.md). GET .../career is league-independent,
 * same endpoint mobile already calls.
 *
 * GET .../quick-view's own `stats.seasons` is a single-current-season tuple
 * by design (see QuickViewStats's docstring in lib/api.ts) — this fetches
 * the real multi-season resume from its own endpoint instead, so a
 * veteran's prior years actually show up here.
 *
 * Only the most recent season renders expanded by default; older ones
 * collapse to just their header until clicked — same as mobile, so several
 * years of history don't all dump onto the page as a wall of stat grids at
 * once.
 */
function CareerSeasonCard({
  season,
  expanded,
  onToggle,
}: {
  season: CareerSeason;
  expanded: boolean;
  onToggle: () => void;
}) {
  const label = `${season.season}${season.current_season ? " (in progress)" : ""}`;
  return (
    <div className="pqv-stat-season" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full flex items-center justify-between gap-2 appearance-none bg-transparent border-0 p-0 cursor-pointer text-left"
      >
        <h3 style={{ margin: 0 }}>
          {label}
          {season.games != null ? ` · ${season.games} games` : ""}
          {season.age != null ? ` · Age ${season.age}` : ""}
        </h3>
        <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </button>
      {expanded ? (
        season.key_stats.length > 0 ? (
          <div className="pqv-stat-grid">
            {season.key_stats.map((item) => (
              <div key={item.label} className="pqv-stat-row">
                <div className="pqv-stat-label">{item.label}</div>
                <div className="pqv-stat-value">{item.value}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="pqv-status-text">No stats recorded for this season.</p>
        )
      ) : null}
    </div>
  );
}

export function PlayerCareerTab({ playerId }: { playerId: string }) {
  const [seasons, setSeasons] = useState<CareerSeason[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState(0);
  // Which player `seasons`/`loadError` actually belong to — same
  // derive-instead-of-reset pattern as PlayerScheduleTab.tsx (avoids a
  // synchronous setState at the top of the effect).
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .getPlayerCareer(playerId)
      .then((result) => {
        if (cancelled) return;
        setSeasons(result.seasons);
        setLoadError(false);
        setExpandedIndex(0);
      })
      .catch(() => {
        if (cancelled) return;
        setSeasons(null);
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoadedFor(playerId);
      });

    return () => {
      cancelled = true;
    };
  }, [playerId]);

  if (loadedFor !== playerId) {
    return <p className="pqv-status-text">Loading career history…</p>;
  }
  if (loadError) {
    return (
      <p className="pqv-status-text" role="alert">
        Couldn&apos;t load this player&apos;s career history right now.
      </p>
    );
  }
  if (!seasons || seasons.length === 0) {
    return <p className="pqv-status-text">No season history available for this player yet.</p>;
  }
  return (
    <div className="flex flex-col">
      {seasons.map((season, index) => (
        <CareerSeasonCard
          key={season.season}
          season={season}
          expanded={expandedIndex === index}
          onToggle={() => setExpandedIndex(expandedIndex === index ? -1 : index)}
        />
      ))}
    </div>
  );
}

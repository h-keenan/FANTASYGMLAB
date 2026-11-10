"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { api, type GamesSeasonSimResponse } from "@/lib/api";
import { formatOdds, formatTitleOdds } from "@/lib/gamesPresentation";

/**
 * Rest-of-season playoff and title odds on the Dashboard, from the same shared
 * Season Simulator the Games tab and the app's dashboard read (GET
 * .../games/season-sim, free for everyone). Renders nothing while loading and
 * whenever the simulator has nothing real to say (offseason, no playoff
 * format, no roster): an absent strip is honest, a made-up one is not.
 * Mirrors mobile's LeagueStandingStrips odds card.
 */
export function oddsStripItems(data: GamesSeasonSimResponse | null): StatStripItem[] | null {
  if (!data || data.reason || !data.my_team) return null;
  const mine = data.my_team;
  const titleAvailable = data.title_odds?.available === true && mine.title_probability != null;
  const playoffValue = mine.clinched ? "Clinched" : mine.eliminated ? "Out" : formatOdds(mine.playoff_probability);
  return [
    {
      glyph: "record",
      label: "Playoff odds",
      value: playoffValue,
      tone: mine.clinched ? "positive" : mine.eliminated ? "risk" : "neutral",
    },
    titleAvailable
      ? { glyph: "power", label: "Title odds", value: formatTitleOdds(mine.title_probability) }
      : { glyph: "franchise", label: "Proj. seed", value: `#${mine.median_seed}` },
    { glyph: "starter", label: "Proj. record", value: `${mine.median_final_wins}-${mine.median_final_losses}` },
  ];
}

export function DashboardOddsStrip({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const [data, setData] = useState<GamesSeasonSimResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGamesSeasonSim(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const items = oddsStripItems(data);
  if (!items || !data) return null;
  const caption = [
    data.weeks_remaining ? `${data.weeks_remaining} weeks left` : null,
    data.trials ? `${data.trials.toLocaleString("en-US")} simulated seasons` : null,
    data.slope_fitted === false ? "early-season estimate" : null,
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <Link
      href={`/games/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
      className="flex flex-col gap-1"
      style={{ color: "inherit", textDecoration: "none" }}
      data-testid="dashboard-odds-strip"
      aria-label="Season odds, open the Season Simulator"
    >
      <StatStrip columns={3} items={items} />
      {caption ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Rest-of-season simulation: {caption}.
        </span>
      ) : null}
    </Link>
  );
}

/**
 * The same season-sim read as DashboardOddsStrip, for a caller that lays the
 * odds tiles out itself (the Dashboard's My Team grid). `items` is null until
 * the simulator has something real to say.
 */
export function useSeasonOdds(leagueId: string, enabled = true): { items: StatStripItem[] | null; caption: string } {
  const [data, setData] = useState<GamesSeasonSimResponse | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api
      .getGamesSeasonSim(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId, enabled]);
  const items = oddsStripItems(data);
  const caption =
    items && data
      ? [
          data.weeks_remaining ? `${data.weeks_remaining} weeks left` : null,
          data.trials ? `${data.trials.toLocaleString("en-US")} simulated seasons` : null,
          data.slope_fitted === false ? "early-season estimate" : null,
        ]
          .filter(Boolean)
          .join(", ")
      : "";
  return { items, caption };
}

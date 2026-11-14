"use client";

import { useEffect, useState } from "react";

import { SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { api } from "@/lib/api";
import type { SimHistorySeason } from "@/lib/simGame";
import { simCareerSeasonParts, simCareerSeasonTitle } from "@/lib/simHistory";

/**
 * The sim's OWN seasons of a player, newest first, under the real career in the Stats tab: one compact module per season played
 * (collapsed: "S3 2028 · 14 g · 212.4 pts · 15.2 avg · WR12"; open: his game log, best week and totals). Read from the game's event log
 * (GET /players/{id}/history), so it covers every season played, the current one included, and saves made before this view existed.
 * The engine stores fantasy points per game (not component stats), so points are what it shows. A rookie has sim seasons only.
 */
export function SimSimSeasons({ gameId, playerId }: { gameId: string; playerId: string }) {
  const [seasons, setSeasons] = useState<SimHistorySeason[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSimPlayerHistory(gameId, playerId).then(
      (body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setSeasons([...(body.seasons ?? [])].sort((a, b) => b.season - a.season));
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId]);

  if (failed) return <p className="pqv-status-text">Could not load this player&apos;s sim seasons.</p>;
  if (seasons == null) return <SkeletonRows count={2} />;
  return (
    <section className="pqv-stat-season flex flex-col gap-2" data-testid="sim-sim-seasons">
      <h3 className="flex items-center gap-2">
        Sim seasons <ToneBadge label="Sim" color="var(--color-accent)" size="xs" />
      </h3>
      {seasons.length === 0 ? (
        <p className="pqv-status-text">No games played in this sim yet. His seasons appear here as the weeks are played.</p>
      ) : (
        seasons.map((s, index) => (
          <CompactModule
            key={s.season}
            id={`simstats.${playerId}.${s.season}`}
            title={simCareerSeasonTitle(s)}
            parts={simCareerSeasonParts(s)}
            defaultOpen={index === 0}
            persist={false}
            testId="sim-season-module"
          >
            <div className="flex flex-col gap-2">
              {s.best_week ? (
                <p className="pqv-status-text">
                  Best week <strong>Wk {s.best_week.week}</strong> ({s.best_week.points.toFixed(1)})
                  {s.teams.length ? <> · {s.teams.map((t) => t.team_name).filter(Boolean).join(", ")}</> : null}
                </p>
              ) : null}
              <ul className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-1.5">
                {(s.weeks ?? []).map((w) => (
                  <li key={`${w.week}-${w.playoff ? "p" : "r"}`} className="flex items-baseline justify-between rounded-md px-2 py-1 text-xs" style={{ background: "var(--glass-input-bg)" }}>
                    <span style={{ color: "var(--color-text-muted)" }}>{w.playoff ? `P${w.week}` : `Wk ${w.week}`}</span>
                    <span className="font-bold tabular-nums">{w.points.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </CompactModule>
        ))
      )}
    </section>
  );
}

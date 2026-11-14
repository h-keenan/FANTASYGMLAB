"use client";

import { useEffect, useState } from "react";

import { ToneBadge } from "@/components/ToneBadge";
import { api, type CareerSeason, type WeeklyStatPoint } from "@/lib/api";
import { simCareerAsOf, simGameLog } from "@/lib/simAsOf";

/**
 * The real-NFL record behind a Fantasy Sim player, cut to the last finished real season at the sim's start (lib/simAsOf.ts):
 * career season by season (GET .../career) and that season's game log (GET .../weekly-stats?season=). Nothing from the season in
 * progress, no news. coridian_, 2026-11-14: "none of these tabs are currently populated ... there should be stats from prior
 * seasons". The quick view's own stats feed is a single in-progress season, which the as-of cut empties, so this fills the Stats tab.
 */
export function SimRealHistory({ playerId, asOf }: { playerId: string; asOf: number }) {
  const [career, setCareer] = useState<CareerSeason[] | null>(null);
  const [log, setLog] = useState<WeeklyStatPoint[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerCareer(playerId)
      .then((body) => {
        if (!cancelled) setCareer(simCareerAsOf(body.seasons, asOf));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    api
      .getPlayerWeeklyStats(playerId, asOf)
      .then((body) => {
        if (!cancelled) setLog(body.weeks);
      })
      .catch(() => {
        if (!cancelled) setLog([]);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, asOf]);

  if (failed) return <p className="pqv-status-text">Could not load past seasons right now.</p>;
  if (career == null) return <p className="pqv-status-text">Loading past seasons…</p>;
  const summary = simGameLog(log ?? []);
  if (career.length === 0 && summary.games === 0) return <p className="pqv-status-text">No NFL seasons on file before this one.</p>;
  return (
    <div className="flex flex-col gap-3" data-testid="sim-real-history">
      {career.length > 0 ? (
        <section className="pqv-stat-season" data-testid="sim-career">
          <h3 className="flex items-center gap-2">Career by season · through {asOf} <ToneBadge label="Real" color="var(--color-text-secondary)" size="xs" /></h3>
          {career.map((season, index) => (
            <div key={season.season} style={{ borderTop: index ? "var(--border-width-default) solid var(--color-border)" : undefined, paddingTop: index ? "0.5rem" : 0 }}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 appearance-none border-0 bg-transparent p-0 text-left"
                aria-expanded={open === index}
                onClick={() => setOpen(open === index ? -1 : index)}
              >
                <span className="text-sm font-bold">
                  {season.season}
                  {season.games != null ? ` · ${season.games} games` : ""}
                  {season.age != null ? ` · Age ${season.age}` : ""}
                </span>
                <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>{open === index ? "▲" : "▼"}</span>
              </button>
              {open === index ? (
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
          ))}
        </section>
      ) : null}
      {summary.games > 0 ? (
        <section className="pqv-stat-season" data-testid="sim-game-log">
          <h3>Game log · {asOf}</h3>
          <p className="pqv-status-text">
            <strong>{summary.games}</strong> games · <strong>{summary.total.toFixed(1)}</strong> pts
            {summary.avg != null ? <> · <strong>{summary.avg.toFixed(1)}</strong> avg</> : null}
            {summary.best ? <> · best Wk {summary.best.week} ({(summary.best.fantasy_points_ppr ?? 0).toFixed(1)})</> : null}
          </p>
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-1.5">
            {summary.weeks.map((w) => (
              <li key={w.week} className="flex items-baseline justify-between rounded-md px-2 py-1 text-xs" style={{ background: "var(--glass-input-bg)" }}>
                <span style={{ color: "var(--color-text-muted)" }}>Wk {w.week}</span>
                <span className="font-bold tabular-nums">{(w.fantasy_points_ppr ?? 0).toFixed(1)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

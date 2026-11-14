"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { SimTeamIdentity, SimTeamLogo } from "@/components/SimTeamIdentity";
import { SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simSeasonText, type SimPlayerHistoryResponse } from "@/lib/simGame";
import { simDraftSlotText, simHistoryText, simWhenLabel } from "@/lib/simHistory";

/**
 * A player's History tab in the Fantasy Sim quick view: where he came from (the round and pick he was drafted at, or
 * the team he started on), every trade, claim and cut since, and a line per season with the team(s) he played for.
 * Derived from the game's event log (GET /players/{id}/history), fetched when the tab opens.
 */
export function SimPlayerHistory({ gameId, playerId }: { gameId: string; playerId: string }) {
  const [data, setData] = useState<SimPlayerHistoryResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.getSimPlayerHistory(gameId, playerId).then(
      (body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setData(body);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId, attempt]);

  if (failed) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="pqv-status-text">Could not load this player&apos;s history.</p>
        <Button size="sm" variant="secondary" onClick={() => { setFailed(false); setAttempt((n) => n + 1); }}>Try again</Button>
      </div>
    );
  }
  if (!data) return <SkeletonRows count={3} />;
  const origin = data.origin;
  const entries = (data.entries ?? []).filter((e) => e !== origin && e.kind !== "drafted" && e.kind !== "started");
  const seasons = data.seasons ?? [];
  return (
    <div className="flex flex-col gap-3" data-testid="sim-player-history">
      <section className="pqv-stat-season" aria-label="Origin">
        <h3>Origin</h3>
        {origin ? (
          <AccentCard accent="var(--color-accent)" compact as="div">
            <div className="flex items-center gap-2">
              {origin.team_name ? <SimTeamLogo name={origin.team_name} size="row" /> : null}
              <div className="flex min-w-0 flex-col">
                <span className="text-sm font-extrabold">{origin.kind === "drafted" ? simDraftSlotText(origin.round, origin.pick, origin.auto) : `Started on ${origin.team_name ?? "a team"}`}</span>
                <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{simHistoryText(origin)}</span>
              </div>
            </div>
            <ToneBadge label={simWhenLabel(origin)} color="var(--color-text-secondary)" size="xs" />
          </AccentCard>
        ) : (
          <p className="pqv-status-text">Not on a team when the game began.</p>
        )}
        {data.current_team?.team_name ? <p className="pqv-status-text">Now with {data.current_team.team_name}.</p> : <p className="pqv-status-text">Free agent.</p>}
      </section>

      <section className="pqv-stat-season" aria-label="Moves">
        <h3>Moves</h3>
        {entries.length === 0 ? (
          <p className="pqv-status-text">No moves yet: still where the draft put him.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {entries.map((e, i) => (
              <li key={i}>
                <AccentCard accent="var(--color-border-strong)" compact as="div">
                  <div className="flex items-center gap-2">
                    <ToneBadge label={simWhenLabel(e)} color="var(--color-text-secondary)" size="xs" />
                    <ToneBadge label={e.kind} color="var(--color-premium)" size="xs" />
                  </div>
                  <p className="text-sm">{simHistoryText(e)}</p>
                </AccentCard>
              </li>
            ))}
          </ul>
        )}
      </section>

      {seasons.length > 0 ? (
        <section className="pqv-stat-season" aria-label="Seasons">
          <h3>Seasons with each team</h3>
          <ul className="flex flex-col gap-2">
            {seasons.map((s) => (
              <li key={s.season}>
                <AccentCard accent="var(--color-border-strong)" compact as="div">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-extrabold">{simSeasonText(s) || `Season ${s.season}`}</span>
                    <span className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
                      {s.games} games · {s.points.toFixed(1)} pts{s.ppg != null ? ` · ${s.ppg.toFixed(1)} ppg` : ""}
                    </span>
                  </div>
                  {s.teams.map((t) => (
                    <div key={t.team_id} className="flex items-center justify-between gap-2 text-xs">
                      {t.team_name ? <SimTeamIdentity name={t.team_name} size="inline" bold={false} nameClassName="text-xs" className="min-w-0" /> : <span />}
                      <span className="tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{t.games} g · {t.ppg.toFixed(1)} ppg</span>
                    </div>
                  ))}
                </AccentCard>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

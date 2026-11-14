"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { PositionBadge } from "@/components/PositionBadge";
import { SimSectionTitle } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simSeasonText, type SimTeamHistoryPick, type SimTeamHistoryResponse } from "@/lib/simGame";
import { simDraftSlotText, simSeasonRecord, simTeamMoveText, simWhenLabel } from "@/lib/simHistory";

function PickRow({ pick }: { pick: SimTeamHistoryPick }) {
  return (
    <li className="flex items-center gap-2 py-1 text-sm" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <PositionBadge position={pick.pos} />
      <span className="min-w-0 flex-1 truncate font-bold">{pick.name}</span>
      <span className="shrink-0 text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
        {simDraftSlotText(pick.round, pick.pick, pick.auto)}
      </span>
    </li>
  );
}

/**
 * A team's History tab: record by season, its draft classes (the league draft and every rookie draft, with the original
 * pick owner when it traded up or down) and every trade, claim and cut. Read from GET /teams/{id}/history, fetched once
 * when the tab opens; derived from the event log, so it is complete for old saves too.
 */
export function SimTeamHistory({ gameId, teamId }: { gameId: string; teamId: string }) {
  const [data, setData] = useState<SimTeamHistoryResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [allMoves, setAllMoves] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSimTeamHistory(gameId, teamId).then(
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
  }, [gameId, teamId, attempt]);

  if (failed) {
    return (
      <div className="flex flex-col items-start gap-2 py-2">
        <p className="text-sm font-bold">Could not load this team&apos;s history.</p>
        <Button size="sm" variant="secondary" onClick={() => { setFailed(false); setAttempt((n) => n + 1); }}>Try again</Button>
      </div>
    );
  }
  if (!data) return <SkeletonCard lines={5} />;
  const seasons = data.seasons ?? [];
  const classes = data.rookie_drafts ?? [];
  const moves = data.moves ?? [];
  const shown = allMoves ? moves : moves.slice(0, 8);
  return (
    <>
      {seasons.length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Record by season">
          <SimSectionTitle glyph="standings" tone="success">Record by season</SimSectionTitle>
          <ul className="flex flex-col gap-1">
            {seasons.map((s) => (
              <li key={s.season}>
                <AccentCard accent={s.champion ? "var(--color-premium)" : "var(--color-border-strong)"} compact as="div">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-extrabold">{simSeasonText(s) || `Season ${s.season}`}</span>
                    <span className="flex items-center gap-2">
                      {s.champion ? <ToneBadge label="Champion" color="var(--color-premium)" size="xs" /> : null}
                      <span className="text-sm font-bold tabular-nums">{simSeasonRecord(s)}</span>
                    </span>
                  </div>
                  <p className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{s.pf.toFixed(1)} PF · {s.pa.toFixed(1)} PA</p>
                </AccentCard>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {(data.draft ?? []).length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="League draft class">
          <SimSectionTitle glyph="spark" tone="accent" note="The league draft, round by round.">Draft class</SimSectionTitle>
          <ul>{data.draft!.map((p) => <PickRow key={p.id} pick={p} />)}</ul>
        </section>
      ) : null}

      {classes.map((c) => (
        <section key={c.year ?? "rookies"} className="flex flex-col gap-1" aria-label={`${c.season_label || c.year || ""} rookie draft`}>
          <SimSectionTitle glyph="spark" tone="accent">{c.year ? `${c.season_label || c.year} rookie draft` : "Rookie draft"}</SimSectionTitle>
          <ul>{c.picks.map((p) => <PickRow key={p.id} pick={p} />)}</ul>
        </section>
      ))}

      <section className="flex flex-col gap-2" aria-label="Transactions">
        <SimSectionTitle glyph="trade" tone="accent" note="Trades, waiver claims and cuts, newest first.">Transactions</SimSectionTitle>
        {moves.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No moves yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {shown.map((m, i) => (
              <li key={i}>
                <AccentCard accent="var(--color-border-strong)" compact as="div">
                  <div className="flex items-center gap-2">
                    <ToneBadge label={simWhenLabel(m)} color="var(--color-text-secondary)" size="xs" />
                    <ToneBadge label={m.kind} color="var(--color-premium)" size="xs" />
                  </div>
                  <p className="text-sm">{simTeamMoveText(m)}</p>
                </AccentCard>
              </li>
            ))}
          </ul>
        )}
        {moves.length > 8 ? (
          <Button size="sm" variant="secondary" onClick={() => setAllMoves((v) => !v)}>{allMoves ? "Show fewer" : `Show all ${moves.length}`}</Button>
        ) : null}
      </section>
    </>
  );
}

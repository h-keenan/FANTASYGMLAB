"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type QuickViewModel, type RankedPlayer, type WeeklyStatPoint } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { WeeklyPointsChart } from "@/components/WeeklyPointsChart";
import {
  buildModelRows,
  buildNarrativePair,
  buildTrendRows,
  buildValueRows,
  compareRowWinner,
  defaultCompareCandidates,
  hasAnyTextValue,
  hasAnyValue,
  searchCompareCandidates,
  type CompareRow,
  type CompareTextRow,
} from "@/lib/playerComparePresentation";

/**
 * Head-to-head Player Compare (Revision 12) — ports app.py's CURRENT,
 * already-layout-fixed render_player_compare_content (PR #1064), not the
 * earlier broken Streamlit version. The identity headers and every
 * comparison row below share the exact same fixed `1fr 6.5rem 1fr` grid
 * (GRID_COLS) — the real fix PR #1064 made (a fixed-width center label
 * column, not `auto`), so every row's value columns land on the identical
 * x-coordinate regardless of how long that row's own label text is, and the
 * identity cards always sit side by side over the matching left/right
 * columns, never stacked. Unlike the Streamlit port, this needs no
 * `flex-wrap:nowrap` workaround: native CSS Grid never auto-stacks a row
 * the way Streamlit's own column-breakpoint behavior did.
 *
 * Data split mirrors mobile's PlayerCompareScreen.tsx: Value & Rank reads
 * straight off the two RankedPlayer rows the caller already fetched from
 * GET .../rankings (score/overall_rank/position_rank/age); Model Breakdown/
 * Trends/Decision Fit each need GET .../players/{id}/quick-view's `model`,
 * fetched once per side only after an opponent is chosen — the same
 * two-call Promise.all mobile's screen makes.
 */

const GRID_COLS = "grid grid-cols-[1fr_6.5rem_1fr] items-center gap-2";

function CompareGridRow({
  left,
  center,
  right,
  isLast,
}: {
  left: React.ReactNode;
  center: React.ReactNode;
  right: React.ReactNode;
  isLast?: boolean;
}) {
  return (
    <div
      data-compare-grid-row=""
      className={`${GRID_COLS} py-2`}
      style={!isLast ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      <div className="flex justify-center min-w-0">{left}</div>
      <div
        className="text-center uppercase font-bold truncate"
        style={{
          color: "var(--color-text-secondary)",
          fontSize: "var(--font-size-badge)",
          letterSpacing: "var(--letter-spacing-badge)",
        }}
      >
        {center}
      </div>
      <div className="flex justify-center min-w-0">{right}</div>
    </div>
  );
}

function ValuePill({ value, format, wins }: { value: number | null; format: (v: number) => string; wins: boolean }) {
  return (
    <span
      className="px-2 py-0.5 text-sm font-bold"
      style={
        wins
          ? { background: "var(--color-success-soft)", border: "var(--border-width-default) solid var(--color-success)", color: "var(--color-success)" }
          : { color: "var(--color-text-primary)", border: "var(--border-width-default) solid transparent" }
      }
    >
      {wins ? (
        <>
          <span aria-hidden="true">✓ </span>
          <span className="sr-only">Better: </span>
        </>
      ) : null}
      {value !== null ? format(value) : "—"}
    </span>
  );
}

function CompareRowView({ row, isLast }: { row: CompareRow; isLast: boolean }) {
  const winner = compareRowWinner(row);
  return (
    <CompareGridRow
      isLast={isLast}
      left={<ValuePill value={row.a} format={row.format} wins={winner === "a"} />}
      center={row.label}
      right={<ValuePill value={row.b} format={row.format} wins={winner === "b"} />}
    />
  );
}

function TextPill({ value }: { value: string | null }) {
  return (
    <span className="text-xs font-semibold text-center" style={{ color: "var(--color-text-primary)" }}>
      {value || "—"}
    </span>
  );
}

function CompareTextRowView({ row, isLast }: { row: CompareTextRow; isLast: boolean }) {
  return (
    <CompareGridRow isLast={isLast} left={<TextPill value={row.a} />} center={row.label} right={<TextPill value={row.b} />} />
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex flex-col gap-0.5 mt-2">
      <span
        className="uppercase font-extrabold"
        style={{ font: "var(--type-supporting-metadata)", color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        Head-to-Head
      </span>
      <h2 className="uppercase" style={{ font: "var(--type-section-title)", letterSpacing: "0.02em" }}>
        {title}
      </h2>
    </div>
  );
}

function IdentityCard({ player }: { player: RankedPlayer }) {
  return (
    <PlayerIdentityTrigger
      identity={{ ...player, sourceLabel: "Player Compare" }}
      className="flex flex-col items-center gap-1 min-w-0 w-full"
    >
      <OvrGauge rating={player.overall_rating ?? null} size="md" />
      <span className="text-sm font-bold text-center truncate w-full" style={{ color: "var(--color-text-primary)" }}>
        {player.name || "Unknown"}
      </span>
      <div className="flex items-center gap-1.5">
        <PositionBadge position={player.position} />
        {player.team ? (
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {player.team}
          </span>
        ) : null}
      </div>
    </PlayerIdentityTrigger>
  );
}

function OpponentPicker({
  basePlayer,
  pool,
  onSelect,
}: {
  basePlayer: RankedPlayer;
  pool: RankedPlayer[];
  onSelect: (player: RankedPlayer) => void;
}) {
  const [search, setSearch] = useState("");
  const candidatePool = useMemo(() => pool.filter((p) => p.player_id !== basePlayer.player_id), [pool, basePlayer.player_id]);
  const suggestions = useMemo(() => defaultCompareCandidates(candidatePool, basePlayer), [candidatePool, basePlayer]);
  const results = useMemo(
    () => (search.trim() ? searchCompareCandidates(candidatePool, search) : suggestions),
    [search, candidatePool, suggestions],
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="glass-surface flex flex-col items-center gap-2 py-4">
        <IdentityCard player={basePlayer} />
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Choose an opponent below.
        </span>
      </div>
      <input
        type="text"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search for a player to compare..."
        className="px-3 py-2 text-sm"
        style={{
          background: "var(--color-surface)",
          border: "var(--border-width-default) solid var(--color-border)",
          color: "var(--color-text-primary)",
        }}
      />
      <div className="glass-surface flex flex-col">
        {results.length === 0 ? (
          <p className="text-sm px-3 py-4" style={{ color: "var(--color-text-muted)" }}>
            No players match.
          </p>
        ) : (
          results.map((candidate) => (
            <button
              key={candidate.player_id}
              type="button"
              onClick={() => onSelect(candidate)}
              className="flex items-center justify-between gap-3 px-3 py-2.5 text-left"
              style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
            >
              <div className="flex items-center gap-2 min-w-0">
                <PositionBadge position={candidate.position} />
                <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                  {candidate.name || "Unknown"}
                </span>
                <span className="text-xs shrink-0" style={{ color: "var(--color-text-muted)" }}>
                  {candidate.team || "—"}
                </span>
              </div>
              <span className="text-sm font-extrabold shrink-0" style={{ color: "var(--color-accent)" }}>
                {candidate.score != null ? Math.round(candidate.score) : "—"}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function NarrativeBlock({
  playerA,
  playerB,
  narrative,
}: {
  playerA: RankedPlayer;
  playerB: RankedPlayer;
  narrative: { a: string | null; b: string | null };
}) {
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3">
      {narrative.a ? (
        <div className="min-w-0">
          <div
            className="uppercase font-bold mb-1"
            style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            {playerA.name || "Player A"}
          </div>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)", lineHeight: "var(--line-height-body)" }}>
            {narrative.a}
          </p>
        </div>
      ) : null}
      {narrative.b ? (
        <div className="min-w-0">
          <div
            className="uppercase font-bold mb-1"
            style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            {playerB.name || "Player B"}
          </div>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)", lineHeight: "var(--line-height-body)" }}>
            {narrative.b}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function PlayerCompareContent({
  leagueName,
  playerA,
  initialPlayerB,
  pool,
}: {
  leagueName: string;
  playerA: RankedPlayer;
  initialPlayerB: RankedPlayer | null;
  pool: RankedPlayer[];
}) {
  const [playerB, setPlayerB] = useState<RankedPlayer | null>(initialPlayerB);
  const [modelA, setModelA] = useState<QuickViewModel | null>(null);
  const [modelB, setModelB] = useState<QuickViewModel | null>(null);
  // Which opponent's models modelA/modelB actually belong to — compared
  // against playerB below to derive "still loading" without a second piece
  // of state set synchronously at the top of the effect (React 19's
  // react-hooks/set-state-in-effect rule flags that pattern; deriving it
  // during render instead of storing it avoids the extra render it'd cause
  // anyway).
  const [modelsLoadedFor, setModelsLoadedFor] = useState<string | null>(null);

  // Points By Week (Revision 14) — its own independent fetch/loaded-for pair,
  // same shape as modelA/modelB/modelsLoadedFor above but kept separate:
  // GET .../weekly-stats is a different endpoint than GET .../quick-view, and
  // a slow chart fetch should never hold up Model Breakdown/Trends/Decision
  // Fit rendering (or vice versa).
  const [weeksA, setWeeksA] = useState<WeeklyStatPoint[]>([]);
  const [weeksB, setWeeksB] = useState<WeeklyStatPoint[]>([]);
  const [weeklySeason, setWeeklySeason] = useState<number | null>(null);
  const [weeklyLoadedFor, setWeeklyLoadedFor] = useState<string | null>(null);

  // Stale modelA/modelB left over from a previous opponent are never
  // rendered while playerB is null (valueRows/modelRows below only read
  // them once playerB is set again), so there is nothing to reset here —
  // just skip the fetch. The next opponent pick re-triggers this effect and
  // overwrites both with fresh data before anything new is displayed.
  useEffect(() => {
    if (!playerB) return;
    let cancelled = false;
    Promise.all([api.getPlayerQuickView(playerA.player_id), api.getPlayerQuickView(playerB.player_id)])
      .then(([a, b]) => {
        if (cancelled) return;
        setModelA(a.model);
        setModelB(b.model);
      })
      .catch(() => {
        if (!cancelled) {
          setModelA(null);
          setModelB(null);
        }
      })
      .finally(() => {
        if (!cancelled) setModelsLoadedFor(playerB.player_id);
      });
    return () => {
      cancelled = true;
    };
  }, [playerA.player_id, playerB]);

  useEffect(() => {
    if (!playerB) return;
    let cancelled = false;
    Promise.all([api.getPlayerWeeklyStats(playerA.player_id), api.getPlayerWeeklyStats(playerB.player_id)])
      .then(([a, b]) => {
        if (cancelled) return;
        setWeeksA(a.weeks);
        setWeeksB(b.weeks);
        setWeeklySeason(a.season);
      })
      .catch(() => {
        if (!cancelled) {
          setWeeksA([]);
          setWeeksB([]);
          setWeeklySeason(null);
        }
      })
      .finally(() => {
        if (!cancelled) setWeeklyLoadedFor(playerB.player_id);
      });
    return () => {
      cancelled = true;
    };
  }, [playerA.player_id, playerB]);

  const loadingModels = playerB !== null && modelsLoadedFor !== playerB.player_id;
  const showWeeklyPoints =
    playerB !== null &&
    weeklyLoadedFor === playerB.player_id &&
    weeklySeason !== null &&
    (weeksA.some((week) => week.fantasy_points_ppr != null) || weeksB.some((week) => week.fantasy_points_ppr != null));
  const valueRows = playerB ? buildValueRows(playerA, playerB) : [];
  const modelRows = playerB ? buildModelRows(modelA, modelB) : [];
  const showModelRows = playerB !== null && hasAnyValue(modelRows);
  const trendRows = playerB ? buildTrendRows(modelA, modelB) : [];
  const showTrendRows = playerB !== null && hasAnyTextValue(trendRows);
  const narrative = playerB ? buildNarrativePair(modelA, modelB) : null;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Player Compare
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      {!playerB ? (
        <OpponentPicker basePlayer={playerA} pool={pool} onSelect={setPlayerB} />
      ) : (
        <div className="flex flex-col gap-5">
          <button
            type="button"
            onClick={() => setPlayerB(null)}
            className="self-start px-3 py-1.5 text-xs font-bold"
            style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            Compare someone else
          </button>

          <div
            data-compare-grid-row=""
            className={`${GRID_COLS} py-3`}
            style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            <IdentityCard player={playerA} />
            <span className="text-center font-extrabold" style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }}>
              VS
            </span>
            <IdentityCard player={playerB} />
          </div>

          {loadingModels ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading model breakdown…
            </p>
          ) : null}

          <section className="flex flex-col gap-2">
            <SectionHeader title="Value & Rank" />
            <div className="glass-surface flex flex-col px-1">
              {valueRows.map((row, index) => (
                <CompareRowView key={row.label} row={row} isLast={index === valueRows.length - 1} />
              ))}
            </div>
          </section>

          {showModelRows ? (
            <section className="flex flex-col gap-2">
              <SectionHeader title="Model Breakdown" />
              <div className="glass-surface flex flex-col px-1">
                {modelRows.map((row, index) => (
                  <CompareRowView key={row.label} row={row} isLast={index === modelRows.length - 1} />
                ))}
              </div>
            </section>
          ) : null}

          {showTrendRows ? (
            <section className="flex flex-col gap-2">
              <SectionHeader title="Trends" />
              <div className="glass-surface flex flex-col px-1">
                {trendRows.map((row, index) => (
                  <CompareTextRowView key={row.label} row={row} isLast={index === trendRows.length - 1} />
                ))}
              </div>
            </section>
          ) : null}

          {narrative ? (
            <section className="flex flex-col gap-2">
              <SectionHeader title="Decision Fit" />
              <NarrativeBlock playerA={playerA} playerB={playerB} narrative={narrative} />
            </section>
          ) : null}

          {showWeeklyPoints ? (
            <section className="flex flex-col gap-2">
              <SectionHeader title="Points By Week" />
              <WeeklyPointsChart
                playerAName={playerA.name || "Player A"}
                playerBName={playerB.name || "Player B"}
                weeksA={weeksA}
                weeksB={weeksB}
                season={weeklySeason as number}
              />
            </section>
          ) : null}
        </div>
      )}
    </main>
  );
}

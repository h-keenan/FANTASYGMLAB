"use client";

import { useEffect, useMemo, useState } from "react";

import { TradePickerSheet } from "@/components/TradePickerSheet";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";

import { api, type QuickViewModel, type RankedPlayer, type ScheduleWeek, type WeeklyStatPoint } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { usePreloadWeeklyPointsChart, WeeklyPointsChart } from "@/components/WeeklyPointsChartLazy";
import {
  buildHeadlineRows,
  buildHeadlineTextRows,
  buildModelRows,
  buildNarrativePair,
  buildTrendRows,
  compareRowWinner,
  hasAnyTextValue,
  hasAnyValue,
  nextProjection,
  ppgFromWeeks,
  readRecentOpponents,
  rememberOpponent,
  scheduleOutlook,
  suggestedOpponents,
  type CompareExtras,
  type CompareRow,
  type CompareTextRow,
} from "@/lib/playerComparePresentation";
import { itemKey, type SheetItem } from "@/lib/tradeSheetPicker";
import { conditionsFor } from "@/lib/tradeSheetPicker";
import { mergeSearchMatches, useLeaguePlayerSearch } from "@/lib/leaguePlayerSearch";
import { ValuesCredit } from "@/components/ValuesCredit";
import { PageTitle } from "@/components/PageTitle";
import { PlayerNameText } from "@/components/PlayerNameText";

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
        className="text-center uppercase font-bold break-words"
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

/** The better side is marked green with a check; the other side is simply quieter gray (no red, no per-row noise). */
function ValuePill({ value, format, wins, quiet }: { value: number | null; format: (v: number) => string; wins: boolean; quiet: boolean }) {
  return (
    <span
      className="px-2 py-0.5 text-sm font-bold tabular-nums"
      style={
        wins
          ? { background: "var(--color-success-soft)", border: "var(--border-width-default) solid var(--color-success)", color: "var(--color-success)" }
          : { color: quiet ? "var(--color-text-muted)" : "var(--color-text-primary)", border: "var(--border-width-default) solid transparent" }
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
      left={<ValuePill value={row.a} format={row.format} wins={winner === "a"} quiet={winner === "b"} />}
      center={row.label}
      right={<ValuePill value={row.b} format={row.format} wins={winner === "b"} quiet={winner === "a"} />}
    />
  );
}

function TextPill({ value, wins, quiet }: { value: string | null; wins?: boolean; quiet?: boolean }) {
  return (
    <span
      className="text-xs font-semibold text-center px-2 py-0.5"
      style={
        wins
          ? { background: "var(--color-success-soft)", border: "var(--border-width-default) solid var(--color-success)", color: "var(--color-success)" }
          : { color: quiet ? "var(--color-text-muted)" : "var(--color-text-primary)", border: "var(--border-width-default) solid transparent" }
      }
    >
      {wins ? <span className="sr-only">Better: </span> : null}
      {value || "—"}
    </span>
  );
}

function CompareTextRowView({ row, isLast }: { row: CompareTextRow; isLast: boolean }) {
  return (
    <CompareGridRow
      isLast={isLast}
      left={<TextPill value={row.a} wins={row.winner === "a"} quiet={row.winner === "b"} />}
      center={row.label}
      right={<TextPill value={row.b} wins={row.winner === "b"} quiet={row.winner === "a"} />}
    />
  );
}


function playerToSheetItem(player: RankedPlayer): SheetItem<RankedPlayer> {
  return {
    key: itemKey("player", player.player_id),
    kind: "player",
    id: player.player_id,
    label: player.name ?? "Player",
    position: player.position,
    team: player.team,
    age: player.age,
    value: player.score,
    conditions: conditionsFor({ injuryStatus: player.injury_status, status: player.status, age: player.age }),
    photoId: player.player_id,
    tier: player.tier,
    injury: player.injury_status,
    ref: player,
  };
}

/**
 * One of the two big slots: photo, value ring, name, position and team, and
 * the value. The whole slot is one tap target that opens the picker; the
 * small info button opens the player card. An empty slot invites a choice.
 */
function CompareSlot({
  label,
  player,
  onChoose,
  onInfo,
  testId,
}: {
  label: string;
  player: RankedPlayer | null;
  onChoose: () => void;
  onInfo?: () => void;
  testId: string;
}) {
  return (
    <div className="glass-surface relative flex min-w-0 flex-col" data-testid={testId} style={player ? undefined : { borderStyle: "dashed", borderColor: "var(--color-border-strong)" }}>
      <button
        type="button"
        onClick={onChoose}
        className="flex min-h-[11rem] w-full min-w-0 flex-col items-center justify-center gap-2 px-3 py-4 text-center"
        aria-label={player ? `${label}: ${player.name}. Change player` : `${label}: choose a player`}
      >
        {player ? (
          <>
            <span className="relative inline-flex">
              <PlayerAvatar playerId={player.player_id} tier={player.tier} size={72} fallbackLabel={(player.name ?? "").split(" ").map((w) => w[0]).slice(0, 2).join("")} />
              <span className="absolute -bottom-1 -right-3">
                <OvrGauge rating={player.overall_rating ?? null} size="sm" />
              </span>
            </span>
            <PlayerNameText name={player.name || "Unknown"} className="w-full text-base font-extrabold" style={{ color: "var(--color-text-primary)" }} />
            <span className="flex items-center gap-1.5">
              <PositionBadge position={player.position} />
              {player.team ? (
                <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  {player.team}
                </span>
              ) : null}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Value{" "}
              <strong className="tabular-nums" style={{ color: "var(--color-accent)" }}>
                {player.score != null ? Math.round(player.score).toLocaleString() : "—"}
              </strong>
            </span>
            <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
              Change
            </span>
          </>
        ) : (
          <>
            <span
              aria-hidden="true"
              className="inline-flex items-center justify-center text-3xl font-light"
              style={{ width: 72, height: 72, borderRadius: "50%", border: "2px dashed var(--color-border-strong)", color: "var(--color-accent)" }}
            >
              +
            </span>
            <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
              Choose a player
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Same position to start
            </span>
          </>
        )}
      </button>
      {player && onInfo ? (
        <button
          type="button"
          onClick={onInfo}
          aria-label={`${player.name} player card`}
          className="absolute right-1 top-1 inline-flex items-center justify-center"
          style={{ width: "var(--touch-target-min)", height: "var(--touch-target-min)", color: "var(--color-text-muted)" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 11v5M12 7.5h.01" />
          </svg>
        </button>
      ) : null}
    </div>
  );
}

/** One-tap opponent chips: suggested (same position, nearby value) and recent. */
function OpponentChips({ label, players, onPick }: { label: string; players: RankedPlayer[]; onPick: (player: RankedPlayer) => void }) {
  if (players.length === 0) return null;
  return (
    <section className="flex flex-col gap-2" aria-label={label}>
      <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {label}
      </span>
      <ul className="flex flex-wrap gap-2">
        {players.map((p) => (
          <li key={p.player_id}>
            <button
              type="button"
              onClick={() => onPick(p)}
              className="glass-surface inline-flex items-center gap-2 py-1 pl-1 pr-3 text-left"
              style={{ minHeight: "var(--touch-target-min)", borderRadius: "var(--radius-pill)" }}
              aria-label={`Compare with ${p.name}`}
            >
              <PlayerAvatar playerId={p.player_id} tier={p.tier} size={32} fallbackLabel={(p.name ?? "").split(" ").map((w) => w[0]).slice(0, 2).join("")} />
              <span className="flex flex-col leading-tight">
                <span className="text-sm font-bold">{p.name}</span>
                <span className="text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                  {p.position} · {p.score != null ? Math.round(p.score).toLocaleString() : "—"}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
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


const NO_EXTRAS: CompareExtras = { ppg: null, projection: null, schedule: null };

export function PlayerCompareContent({
  leagueId,
  leagueName,
  playerA: initialPlayerA,
  initialPlayerB,
  pool,
}: {
  leagueId: string;
  leagueName: string;
  playerA: RankedPlayer;
  initialPlayerB: RankedPlayer | null;
  pool: RankedPlayer[];
}) {
  usePreloadWeeklyPointsChart();
  const { openPlayer } = usePlayerQuickView();
  const [playerA, setPlayerA] = useState<RankedPlayer>(initialPlayerA);
  const [playerB, setPlayerB] = useState<RankedPlayer | null>(initialPlayerB);
  const [picking, setPicking] = useState<"a" | "b" | null>(null);
  const [pickSearch, setPickSearch] = useState("");
  const [moreOpen, setMoreOpen] = useState(false);
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [modelA, setModelA] = useState<QuickViewModel | null>(null);
  const [modelB, setModelB] = useState<QuickViewModel | null>(null);
  // Which pair the models/weeks/schedules belong to, so "still loading" is derived at render time instead of
  // by a synchronous setState at the top of an effect.
  const pairKey = playerB ? `${playerA.player_id}|${playerB.player_id}` : null;
  const [modelsLoadedFor, setModelsLoadedFor] = useState<string | null>(null);
  const [weeksA, setWeeksA] = useState<WeeklyStatPoint[]>([]);
  const [weeksB, setWeeksB] = useState<WeeklyStatPoint[]>([]);
  const [weeklySeason, setWeeklySeason] = useState<number | null>(null);
  const [weeklyLoadedFor, setWeeklyLoadedFor] = useState<string | null>(null);
  const [scheduleA, setScheduleA] = useState<ScheduleWeek[]>([]);
  const [scheduleB, setScheduleB] = useState<ScheduleWeek[]>([]);
  const [scheduleLoadedFor, setScheduleLoadedFor] = useState<string | null>(null);

  // Recents live in localStorage, so read them after mount.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRecentIds(readRecentOpponents(leagueId));
  }, [leagueId]);

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
        if (!cancelled) setModelsLoadedFor(`${playerA.player_id}|${playerB.player_id}`);
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
        if (!cancelled) setWeeklyLoadedFor(`${playerA.player_id}|${playerB.player_id}`);
      });
    return () => {
      cancelled = true;
    };
  }, [playerA.player_id, playerB]);

  useEffect(() => {
    if (!playerB) return;
    let cancelled = false;
    Promise.all([api.getPlayerSchedule(playerA.player_id), api.getPlayerSchedule(playerB.player_id)])
      .then(([a, b]) => {
        if (cancelled) return;
        setScheduleA(a.weeks ?? []);
        setScheduleB(b.weeks ?? []);
      })
      .catch(() => {
        if (!cancelled) {
          setScheduleA([]);
          setScheduleB([]);
        }
      })
      .finally(() => {
        if (!cancelled) setScheduleLoadedFor(`${playerA.player_id}|${playerB.player_id}`);
      });
    return () => {
      cancelled = true;
    };
  }, [playerA.player_id, playerB]);

  // Typed searches also ask the server, so players below the loaded rankings window are found.
  const searchMatches = useLeaguePlayerSearch(leagueId, "Dynasty", picking ? pickSearch : "");
  const searchPool = useMemo(() => mergeSearchMatches(pool, searchMatches), [pool, searchMatches]);
  const sheetItems = useMemo(() => {
    if (!picking) return [];
    const skip = new Set(picking === "a" ? [playerB?.player_id] : [playerA.player_id]);
    return searchPool.filter((p) => !skip.has(p.player_id)).map(playerToSheetItem);
  }, [picking, searchPool, playerA.player_id, playerB]);
  // Opens pre-filtered to the position of the player being compared against; one tap on Clear shows everyone.
  const sheetPosition = (picking === "b" ? playerA.position : picking === "a" ? (playerB?.position ?? playerA.position) : null) ?? null;

  const suggested = useMemo(
    () => suggestedOpponents(pool, playerA, recentIds, 4),
    [pool, playerA, recentIds],
  );
  const recent = useMemo(
    () => recentIds.map((id) => pool.find((p) => p.player_id === id)).filter((p): p is RankedPlayer => Boolean(p) && p!.player_id !== playerA.player_id).slice(0, 4),
    [recentIds, pool, playerA.player_id],
  );

  function choose(player: RankedPlayer) {
    if (picking === "a") setPlayerA(player);
    else setPlayerB(player);
    setRecentIds(rememberOpponent(leagueId, player.player_id));
    setPicking(null);
  }

  const loaded = (key: string | null, done: string | null) => key !== null && done === key;
  const loadingModels = pairKey !== null && !loaded(pairKey, modelsLoadedFor);
  const scheduleReady = loaded(pairKey, scheduleLoadedFor);
  const weeklyReady = loaded(pairKey, weeklyLoadedFor);
  const extrasA: CompareExtras = playerB
    ? { ppg: weeklyReady ? ppgFromWeeks(weeksA) : null, projection: scheduleReady ? nextProjection(scheduleA) : null, schedule: scheduleReady ? scheduleOutlook(scheduleA) : null }
    : NO_EXTRAS;
  const extrasB: CompareExtras = playerB
    ? { ppg: weeklyReady ? ppgFromWeeks(weeksB) : null, projection: scheduleReady ? nextProjection(scheduleB) : null, schedule: scheduleReady ? scheduleOutlook(scheduleB) : null }
    : NO_EXTRAS;
  const showWeeklyPoints =
    playerB !== null &&
    weeklyReady &&
    weeklySeason !== null &&
    (weeksA.some((week) => week.fantasy_points_ppr != null) || weeksB.some((week) => week.fantasy_points_ppr != null));
  const headlineRows = playerB ? buildHeadlineRows(playerA, playerB, extrasA, extrasB) : [];
  const headlineTextRows = playerB ? buildHeadlineTextRows(modelA, modelB, extrasA, extrasB) : [];
  const modelRows = playerB ? buildModelRows(modelA, modelB) : [];
  const showModelRows = playerB !== null && hasAnyValue(modelRows);
  const roleRows = playerB ? buildTrendRows(modelA, modelB).filter((row) => row.label === "Role Trend") : [];
  const showRoleRows = playerB !== null && hasAnyTextValue(roleRows);
  const narrative = playerB ? buildNarrativePair(modelA, modelB) : null;
  const hasMore = showModelRows || showRoleRows || Boolean(narrative) || showWeeklyPoints;

  return (
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page="Player Compare" leagueName={leagueName} />
      </header>

      <div className="mx-auto flex w-full flex-col gap-4" style={{ maxWidth: "52rem" }}>
        <section className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 sm:gap-3" aria-label="Players to compare">
          <CompareSlot testId="compare-slot-a" label="Player A" player={playerA} onChoose={() => { setPickSearch(""); setPicking("a"); }} onInfo={() => openPlayer({ ...playerA, leagueId, leagueName, sourceLabel: "Player Compare" })} />
          <span className="text-center font-extrabold" style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }} aria-hidden="true">
            VS
          </span>
          <CompareSlot testId="compare-slot-b" label="Player B" player={playerB} onChoose={() => { setPickSearch(""); setPicking("b"); }} onInfo={playerB ? () => openPlayer({ ...playerB, leagueId, leagueName, sourceLabel: "Player Compare" }) : undefined} />
        </section>

        {!playerB ? (
          <>
            <OpponentChips label="Suggested" players={suggested} onPick={(p) => choose({ ...p })} />
            <OpponentChips label="Recent" players={recent} onPick={(p) => choose({ ...p })} />
          </>
        ) : (
          <>
            {loadingModels ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                Loading the full breakdown…
              </p>
            ) : null}

            <section className="flex flex-col gap-2" aria-label="Head-to-head">
              <div className="glass-surface flex flex-col px-3 py-1" data-testid="compare-grid">
                <div className={`${GRID_COLS} pt-2 text-center text-xs font-extrabold`} style={{ color: "var(--color-text-secondary)" }}>
                  <span className="truncate">{playerA.name}</span>
                  <span aria-hidden="true" />
                  <span className="truncate">{playerB.name}</span>
                </div>
                {headlineRows.map((row, index) => (
                  <CompareRowView key={row.label} row={row} isLast={index === headlineRows.length - 1 && headlineTextRows.length === 0} />
                ))}
                {headlineTextRows.map((row, index) => (
                  <CompareTextRowView key={row.label} row={row} isLast={index === headlineTextRows.length - 1} />
                ))}
              </div>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Green marks the better side of each row.
              </p>
            </section>

            {hasMore ? (
              <section className="flex flex-col gap-3">
                <button
                  type="button"
                  className="glass-surface flex w-full items-center justify-between px-3 text-left text-sm font-bold"
                  style={{ minHeight: "var(--touch-target-min)" }}
                  aria-expanded={moreOpen}
                  aria-controls="compare-more"
                  onClick={() => setMoreOpen((v) => !v)}
                >
                  More stats
                  <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>{moreOpen ? "−" : "+"}</span>
                </button>
                {moreOpen ? (
                  <div id="compare-more" className="flex flex-col gap-4">
                    {showModelRows ? (
                      <section className="flex flex-col gap-2">
                        <SectionHeading kicker="Head-to-Head" className="flex flex-col gap-0.5">Model Breakdown</SectionHeading>
                        <div className="glass-surface flex flex-col px-3">
                          {modelRows.map((row, index) => (
                            <CompareRowView key={row.label} row={row} isLast={index === modelRows.length - 1} />
                          ))}
                        </div>
                      </section>
                    ) : null}
                    {showRoleRows ? (
                      <div className="glass-surface flex flex-col px-3">
                        {roleRows.map((row, index) => (
                          <CompareTextRowView key={row.label} row={row} isLast={index === roleRows.length - 1} />
                        ))}
                      </div>
                    ) : null}
                    {narrative ? (
                      <section className="flex flex-col gap-2">
                        <SectionHeading kicker="Head-to-Head" className="flex flex-col gap-0.5">Decision Fit</SectionHeading>
                        <NarrativeBlock playerA={playerA} playerB={playerB} narrative={narrative} />
                      </section>
                    ) : null}
                    {showWeeklyPoints ? (
                      <section className="flex flex-col gap-2">
                        <SectionHeading kicker="Head-to-Head" className="flex flex-col gap-0.5">Points By Week</SectionHeading>
                        <WeeklyPointsChart playerAName={playerA.name || "Player A"} playerBName={playerB.name || "Player B"} weeksA={weeksA} weeksB={weeksB} season={weeklySeason as number} />
                      </section>
                    ) : null}
                  </div>
                ) : null}
              </section>
            ) : null}

            <OpponentChips label="Try another" players={suggested.slice(0, 4)} onPick={(p) => choose({ ...p })} />
          </>
        )}
      </div>

      {picking ? (
        <TradePickerSheet
          key={picking}
          mode="single"
          title={picking === "a" ? "Choose Player A" : "Choose a player to compare"}
          subtitle={sheetPosition ? `${sheetPosition} shown first. Clear the filter to see everyone.` : undefined}
          tone="neutral"
          items={sheetItems}
          initialSelected={[]}
          initialFilters={{ positions: sheetPosition ? [sheetPosition.toUpperCase()] : [], conditions: [] }}
          onApply={(keys) => {
            const chosen = sheetItems.find((i) => i.key === keys[0]);
            if (chosen) choose(chosen.ref as RankedPlayer);
          }}
          onClose={() => setPicking(null)}
          onSearch={setPickSearch}
          onInfo={(item) => openPlayer({ ...(item.ref as RankedPlayer), leagueId, leagueName, sourceLabel: "Player Compare" })}
        />
      ) : null}
      <ValuesCredit />
    </main>
  );
}

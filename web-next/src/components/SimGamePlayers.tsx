"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { Collapsible } from "@/components/Collapsible";
import { PlayerQuickView } from "@/components/PlayerQuickView";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { EmptyState } from "@/components/EmptyState";
import { Input, Select } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimPager, SimPlayerLine, SimStat, SimToneBadge, useSimDebounced, useSimWide } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { SIM_WINDOW_STEP, simWindow } from "@/lib/simLayout";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  SIM_STATUS_OPTIONS,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtProjection,
  simFmtPts,
  simFmtValue,
  simHeadshotId,
  simOwnerLabel,
  simOwnerTone,
  simPageCount,
  simPlayerStatusLabel,
  type SimGamePlayer,
  type SimPlayerDetailResponse,
  type SimPlayerFilter,
  type SimPlayerSort,
  type SimPlayerStatusFilter,
  type SimPos,
} from "@/lib/simGame";

/**
 * Searchable, filterable, sortable table of every player in the game: owner
 * (you / AI team / free agent), projection and value. Used as the draft board
 * (status fixed to "available") and as the weekly Players tab. Server-side
 * paging and filtering (GET /players); a changed filter returns to page 1
 * (simFilterReducer) and a late response for an old filter is ignored.
 */
export function SimPlayerBrowser({
  gameId,
  fixedStatus,
  initial,
  actions,
  onOpen,
  refreshKey = 0,
  showStatusFilter = true,
  onItems,
  emptyTitle = "No players match",
  positions = SIM_POSITIONS,
}: {
  gameId: string;
  /** Positions this league plays (no K / DEF chips when it has no such slot). */
  positions?: SimPos[];
  /** Lock the status filter (the draft board is always free agents). */
  fixedStatus?: SimPlayerStatusFilter;
  initial?: Partial<SimPlayerFilter>;
  actions?: (player: SimGamePlayer) => ReactNode;
  onOpen: (player: SimGamePlayer) => void;
  /** Bump to refetch after a pick / add / trade. */
  refreshKey?: number;
  showStatusFilter?: boolean;
  onItems?: (items: SimGamePlayer[]) => void;
  emptyTitle?: string;
}) {
  const [filter, dispatch] = useReducer(simFilterReducer, simDefaultFilter({ status: fixedStatus ?? "", ...initial }));
  const [text, setText] = useState(filter.q);
  const debouncedText = useSimDebounced(text, PLAYER_SEARCH_DEBOUNCE_MS);
  const [items, setItems] = useState<SimGamePlayer[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const wide = useSimWide();
  // A new page or filter starts at the top window again (the window is keyed to the filter).
  const windowKey = [filter.page, filter.pos, filter.sort, filter.q, filter.status].join("|");
  const [win, setWin] = useState({ key: windowKey, n: SIM_WINDOW_STEP });
  const visible = win.key === windowKey ? win.n : SIM_WINDOW_STEP;
  const setVisible = (update: (n: number) => number) => setWin({ key: windowKey, n: update(visible) });

  useEffect(() => {
    dispatch({ type: "q", value: debouncedText });
  }, [debouncedText]);

  const query = useMemo(() => simFilterQuery({ ...filter, status: fixedStatus ?? filter.status }), [filter, fixedStatus]);

  useEffect(() => {
    const controller = new AbortController();
    api
      .getSimGamePlayers(gameId, query, controller.signal)
      .then((body) => {
        if (controller.signal.aborted) return;
        setItems(body.items ?? []);
        setTotal(body.total ?? 0);
        setState("ready");
        onItems?.(body.items ?? []);
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
    // onItems is a stable setter from the caller; refetch on refreshKey / retry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, query, refreshKey, attempt]);

  const rows = simWindow(items, wide ? items.length : visible);
  return (
    <section className="flex flex-col gap-3" aria-label="Players">
      <Input
        type="search"
        inputMode="search"
        placeholder="Search players or NFL teams"
        aria-label="Search players"
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full"
      />
      <PillRow
        ariaLabel="Position filter"
        variant="scroll"
        options={[{ label: "All", value: "" }, ...positions.map((pos) => ({ label: pos, value: pos }))]}
        active={filter.pos}
        onSelect={(value) => dispatch({ type: "pos", value: value as SimPos | "" })}
      />
      <div className="flex gap-2">
        {showStatusFilter && !fixedStatus ? (
          <label className="flex flex-1 flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
            Show
            <Select
              aria-label="Status filter"
              value={filter.status}
              onChange={(event) => dispatch({ type: "status", value: event.target.value as SimPlayerStatusFilter })}
            >
              {SIM_STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>
        ) : null}
        <label className="flex flex-1 flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          Sort by
          <Select
            aria-label="Sort players"
            value={filter.sort}
            onChange={(event) => dispatch({ type: "sort", value: event.target.value as SimPlayerSort })}
          >
            {SIM_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
      </div>
      {state === "loading" && items.length === 0 ? (
        <SkeletonRows count={6} />
      ) : state === "error" ? (
        <EmptyState
          title="Could not load players"
          subtitle="Check your connection and try again."
          actionLabel="Try again"
          onAction={() => setAttempt((n) => n + 1)}
        />
      ) : items.length === 0 ? (
        <EmptyState title={emptyTitle} subtitle="Try a different search or filter." />
      ) : (
        <div className="flex flex-col" style={{ opacity: state === "loading" ? 0.6 : 1 }}>
          <p className="text-xs pb-1" style={{ color: "var(--color-text-muted)" }} aria-live="polite">
            {total} player{total === 1 ? "" : "s"}
          </p>
          {rows.shown.map((player) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              onOpen={onOpen}
              extra={
                <span className="flex flex-wrap items-center gap-1.5">
                  {player.owner ? <SimToneBadge label={simOwnerLabel(player.owner)} tone={simOwnerTone(player.owner)} /> : null}
                  {player.adp != null ? (
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      ADP {simFmtValue(player.adp)}
                    </span>
                  ) : null}
                </span>
              }
              trailing={
                <>
                  <SimStat label="Proj" value={simFmtPts(player.projection)} />
                  <span className="hidden sm:block"><SimStat label="Value" value={simFmtValue(player.value)} /></span>
                  {actions ? actions(player) : null}
                </>
              }
            />
          ))}
          {rows.remaining > 0 ? (
            <button
              type="button"
              className="tap-link self-center text-sm font-bold"
              style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
              onClick={() => setVisible((n) => n + SIM_WINDOW_STEP)}
            >
              Show {Math.min(SIM_WINDOW_STEP, rows.remaining)} more on this page ({rows.remaining} left)
            </button>
          ) : null}
        </div>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: "page", value: page })} />
    </section>
  );
}

/**
 * The game's player detail IS the main app's Player Quick View: the shared
 * PlayerQuickView (hero, news, stats, trends, bio, model) fed by an adapter
 * that maps the sim player to a quick-view identity (real Sleeper id ->
 * real data from the main API), plus a sim overlay with what only this game
 * knows: this week's projection band, status, owner, week-by-week outlook,
 * results so far and sim news. A synthetic player (no real id) renders the
 * same layout without the remote sections.
 */
export function SimPlayerSheet({ gameId, player, onClose, actions }: { gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode }) {
  const real = simHeadshotId(player);
  const identity: PlayerQuickViewIdentity = {
    player_id: real ?? player.id,
    name: player.name,
    position: player.pos,
    team: player.team ?? null,
    age: player.age ?? null,
    injury_status: player.status === "out" ? "Out" : null,
    sourceLabel: "Fantasy Sim",
  };
  return <PlayerQuickView identity={identity} onClose={onClose} remote={Boolean(real)} simOverlay={<SimPlayerOverlay gameId={gameId} player={player} actions={actions} />} />;
}

/** The sim-only sections of the player detail, as phone-friendly collapsibles. */
export function SimPlayerOverlay({ gameId, player, actions }: { gameId: string; player: SimGamePlayer; actions?: ReactNode }) {
  const [detail, setDetail] = useState<SimPlayerDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .getSimGamePlayer(gameId, player.id)
      .then((body) => {
        if (!cancelled) setDetail(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, player.id]);

  const live = detail?.player ?? player;
  const status = simPlayerStatusLabel(live);
  const weeks = detail?.weeks ?? [];
  const maxCeiling = Math.max(1, ...weeks.map((w) => w.ceiling));
  return (
    <div className="flex flex-col gap-2 pt-2" data-testid="sim-player-overlay">
      <Collapsible
        id="player.sim"
        accent="var(--color-accent)"
        defaultOpen
        title="In this game"
        summary={
          <span className="flex items-center gap-1">
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {live.owner ? <SimToneBadge label={simOwnerLabel(live.owner)} tone={simOwnerTone(live.owner)} /> : null}
          </span>
        }
      >
        <div className="grid grid-cols-3 gap-2">
          <div className="flex flex-col">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>This week</span>
            <span className="text-base font-extrabold">{simFmtPts(live.projection)}</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simFmtPts(live.floor)}-{simFmtPts(live.ceiling)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }} title="Model value on the game's 0-100 scale">Value</span>
            <span className="text-base font-extrabold">{simFmtValue(live.value)}</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>ADP {simFmtValue(live.adp)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Season</span>
            <span className="text-base font-extrabold">{simFmtPts(live.season_points ?? 0)}</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{live.games ?? 0} games</span>
          </div>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </Collapsible>
      {failed ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Could not load the full outlook.</p>
      ) : !detail ? (
        <SkeletonRows count={2} />
      ) : (
        <>
          {weeks.length > 0 ? (
            <Collapsible id="player.sim.weeks" accent="var(--color-accent)" defaultOpen={false} title="Week by week" summary={<span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{weeks.length} weeks</span>}>
              <ol className="flex flex-col gap-1.5" aria-label="Week-by-week projection">
                {weeks.map((w) => (
                  <li key={w.week} className="flex items-center gap-2 text-xs">
                    <span className="w-8 shrink-0 font-bold" style={{ color: "var(--color-text-muted)" }}>W{w.week}</span>
                    {w.bye || w.out ? (
                      <span style={{ color: w.out ? "var(--color-danger)" : "var(--color-warning)" }}>{w.out ? "Out" : "Bye"}</span>
                    ) : (
                      <>
                        <span
                          className="relative h-2 flex-1 overflow-hidden"
                          style={{ background: "var(--color-surface-muted)", borderRadius: "var(--radius-pill)" }}
                          role="img"
                          aria-label={`Projection ${simFmtPts(w.projection)}, range ${simFmtPts(w.floor)} to ${simFmtPts(w.ceiling)}`}
                        >
                          <span
                            className="absolute inset-y-0"
                            style={{
                              left: `${(w.floor / maxCeiling) * 100}%`,
                              width: `${Math.max(2, ((w.ceiling - w.floor) / maxCeiling) * 100)}%`,
                              background: "var(--color-accent-soft)",
                              borderRadius: "var(--radius-pill)",
                            }}
                          />
                          <span className="absolute inset-y-0" style={{ left: `${(w.projection / maxCeiling) * 100}%`, width: 3, background: "var(--color-accent-strong)" }} />
                        </span>
                        <span className="w-24 shrink-0 text-right font-semibold">{simFmtProjection(w)}</span>
                      </>
                    )}
                  </li>
                ))}
              </ol>
            </Collapsible>
          ) : null}
          {(detail.history ?? []).length > 0 ? (
            <Collapsible id="player.sim.results" accent="var(--color-success)" defaultOpen title="Results so far">
              <ul className="flex flex-wrap gap-2">
                {detail.history!.map((h) => (
                  <li key={h.week} className="glass-surface px-3 py-1 text-xs">
                    <span style={{ color: "var(--color-text-muted)" }}>W{h.week} </span>
                    <span className="font-bold">{simFmtPts(h.points)}</span>
                  </li>
                ))}
              </ul>
            </Collapsible>
          ) : null}
          {(detail.news ?? []).length > 0 ? (
            <Collapsible id="player.sim.news" accent="var(--color-warning)" defaultOpen title="Game news">
              <ul className="flex flex-col gap-1.5">
                {detail.news!.map((n, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <ReviewGlyphChip glyph="stats" tone="accent" size={22} />
                    <span className="min-w-0 flex-1">
                      <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>Week {n.week} · </span>
                      {n.text}
                    </span>
                  </li>
                ))}
              </ul>
            </Collapsible>
          ) : null}
        </>
      )}
    </div>
  );
}

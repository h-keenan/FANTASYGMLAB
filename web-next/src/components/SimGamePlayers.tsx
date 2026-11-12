"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { EmptyState } from "@/components/EmptyState";
import { Input, Select } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { SimPager, SimPlayerLine, SimSheet, SimStat, SimToneBadge, useSimDebounced } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { PositionBadge } from "@/components/PositionBadge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { api } from "@/lib/api";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  SIM_STATUS_OPTIONS,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtAge,
  simFmtProjection,
  simFmtPts,
  simFmtValue,
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
          {items.map((player) => (
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
                  <SimStat label="Value" value={simFmtValue(player.value)} />
                  {actions ? actions(player) : null}
                </>
              }
            />
          ))}
        </div>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: "page", value: page })} />
    </section>
  );
}

/** Player sheet: this week's projection and band, week-by-week outlook, results so far, news. */
export function SimPlayerSheet({ gameId, player, onClose, actions }: { gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode }) {
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
    <SimSheet title={`${player.name} details`} onClose={onClose}>
      <div className="flex items-center gap-3 pr-10">
        <PlayerAvatar playerId={player.id} size={56} />
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-lg font-extrabold break-words">{player.name}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
            <PositionBadge position={live.pos} />
            <span>{live.team ?? "Free agent"}</span>
            {simFmtAge(live.age) ? <span>Age {simFmtAge(live.age)}</span> : null}
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {live.owner ? <SimToneBadge label={simOwnerLabel(live.owner)} tone={simOwnerTone(live.owner)} /> : null}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 pt-3">
        <AccentCard accent="var(--color-accent)" compact as="div">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>This week</span>
          <span className="text-base font-extrabold">{simFmtPts(live.projection)}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simFmtPts(live.floor)}-{simFmtPts(live.ceiling)}</span>
        </AccentCard>
        <AccentCard accent="var(--color-premium)" compact as="div">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Value</span>
          <span className="text-base font-extrabold">{simFmtValue(live.value)}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>ADP {simFmtValue(live.adp)}</span>
        </AccentCard>
        <AccentCard accent="var(--color-success)" compact as="div">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Season</span>
          <span className="text-base font-extrabold">{simFmtPts(live.season_points ?? 0)}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{live.games ?? 0} games</span>
        </AccentCard>
      </div>
      {actions ? <div className="flex flex-wrap gap-2 pt-3">{actions}</div> : null}
      {failed ? (
        <p className="pt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>Could not load the full outlook.</p>
      ) : !detail ? (
        <div className="pt-3"><SkeletonRows count={3} /></div>
      ) : (
        <>
          {weeks.length > 0 ? (
            <div className="flex flex-col gap-2 pt-4">
              <SectionHeading note="Projection with its floor-to-ceiling band for each remaining week.">Week by week</SectionHeading>
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
                          <span
                            className="absolute inset-y-0"
                            style={{ left: `${(w.projection / maxCeiling) * 100}%`, width: 3, background: "var(--color-accent-strong)" }}
                          />
                        </span>
                        <span className="w-24 shrink-0 text-right font-semibold">{simFmtProjection(w)}</span>
                      </>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          {(detail.history ?? []).length > 0 ? (
            <div className="flex flex-col gap-2 pt-4">
              <SectionHeading>Results so far</SectionHeading>
              <ul className="flex flex-wrap gap-2">
                {detail.history!.map((h) => (
                  <li key={h.week} className="glass-surface px-3 py-1 text-xs">
                    <span style={{ color: "var(--color-text-muted)" }}>W{h.week} </span>
                    <span className="font-bold">{simFmtPts(h.points)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {(detail.news ?? []).length > 0 ? (
            <div className="flex flex-col gap-2 pt-4">
              <SectionHeading>News</SectionHeading>
              <ul className="flex flex-col gap-1.5">
                {detail.news!.map((n, i) => (
                  <li key={i} className="text-sm">
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Week {n.week} · </span>
                    {n.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </SimSheet>
  );
}

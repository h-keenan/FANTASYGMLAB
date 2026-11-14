"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { simAsOfSeason } from "@/lib/simAsOf";
import { PlayerQuickView, StatGroup, type SimPqvSections } from "@/components/PlayerQuickView";
import { SimRealHistory } from "@/components/SimRealHistory";
import { SimPlayerHistory } from "@/components/SimPlayerHistory";
import { SimScoutingSections } from "@/components/SimScoutingSections";
import { WeeklyPointsPanel } from "@/components/WeeklyPointsChartLazy";
import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { EmptyState } from "@/components/EmptyState";
import { Input, Select } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimDraftRow } from "@/components/SimDraftBoard";
import { SimPager, SimToneBadge, useSimDebounced, useSimWide } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { SIM_WINDOW_STEP, simWindow } from "@/lib/simLayout";
import { simSuppressedBadges } from "@/lib/simDraft";
import { simActualPoints, simAvailabilityLine, simHeaderTags, simHeroFeed, simProjectionBand, simProjectionIsFlat, simRosLine } from "@/lib/simPlayerSheet";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  simStatusOptions,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtPts,
  simProjText,
  simFmtValue,
  simHeadshotId,
  simIfStartsHint,
  simPlayerTags,
  simOwnerLabel,
  simOwnerTone,
  simRoleBadge,
  simPageCount,
  simPlayerStatusLabel,
  type SimGamePlayer,
  type SimPlayerDetailResponse,
  type SimPlayerFilter,
  type SimPlayerSort,
  type SimPlayerStatusFilter,
  type SimPosFilter,
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
  week = 0,
  blockEnabled = false,
  positions = SIM_POSITIONS.map((pos) => ({ label: pos as string, value: pos as SimPosFilter })),
}: {
  gameId: string;
  /** Current game week, to flag a bye that is close. */
  week?: number;
  /** The game has a trade block: adds the "On the block" status filter. */
  blockEnabled?: boolean;
  /** Filter pills after "All" (simFilterPositionsFor). */
  positions?: { label: string; value: SimPosFilter }[];
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

  const suppressed = simSuppressedBadges(items);
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
        options={[{ label: "All", value: "" }, ...positions]}
        active={filter.pos}
        onSelect={(value) => dispatch({ type: "pos", value: value as SimPosFilter | "" })}
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
              {simStatusOptions(blockEnabled).map((option) => (
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
            <SimDraftRow
              key={player.id}
              suppressBadges={suppressed}
              player={player}
              week={week}
              onOpen={onOpen}
              tags={simPlayerTags(player)}
              actions={actions ? actions(player) : null}
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
 * PlayerQuickView (hero tiles, news, stats, trends, bio, model) fed by an
 * adapter that maps the sim player to a quick-view identity (real Sleeper id
 * -> real data from the main API; a generated player has no real data, so the
 * hero tiles take the sim's own value and ranks), plus sim sections rendered
 * with the quick view's own section classes and its own weekly chart: this
 * sim season's actual points, the rest-of-season band when it truly varies by
 * week, and a one-line summary when it does not.
 */
export function SimPlayerSheet({ gameId, player, onClose, actions, startYear, seasonLabel }: { /** The sim's current season, "S3 2028": names the season tile and the week-by-week header. */ seasonLabel?: string | null; gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode; /** game.settings.start_year: drives the as-of cut of real data. */ startYear?: number | null }) {
  const detail = useSimPlayerDetail(gameId, player.id);
  const live = detail.data?.player ?? player;
  const real = simHeadshotId(player);
  // A real player's hero tiles come from the real data behind his id; only a generated player (no real data) takes the sim's own numbers.
  const feed = real ? null : simHeroFeed(live);
  const identity: PlayerQuickViewIdentity = {
    player_id: real ?? player.id,
    name: player.name,
    position: player.pos,
    team: player.team ?? null,
    age: player.age ?? null,
    injury_status: live.status === "out" ? "Out" : null,
    sourceLabel: "Fantasy Sim",
    // The header carries the same tags the list row showed (the one injury chip, owner / Free agent, role, block).
    tags: simHeaderTags(live),
    // The list rows' Overall also drives the hero's Player score ring (real and generated players alike), so the
    // number never differs between a row and its quick view. The model's internal rating is never shown.
    overall_rating: live.overall ?? null,
    ...(feed ? { overall_rank: feed.overall_rank, position_rank: feed.position_rank } : {}),
  };
  return <PlayerQuickView identity={identity} onClose={onClose} remote={Boolean(real)} asOfSeason={simAsOfSeason(startYear)} simSections={simPqvSections(gameId, live, detail, actions, seasonLabel, real ? { playerId: real, asOf: simAsOfSeason(startYear) } : undefined)} />;
}

interface SimPlayerDetailState {
  data: SimPlayerDetailResponse | null;
  failed: boolean;
}

function useSimPlayerDetail(gameId: string, playerId: string): SimPlayerDetailState {
  const [state, setState] = useState<SimPlayerDetailState & { key: string }>({ data: null, failed: false, key: "" });
  const key = `${gameId}/${playerId}`;
  useEffect(() => {
    let cancelled = false;
    api
      .getSimGamePlayer(gameId, playerId)
      .then((body) => {
        if (!cancelled) setState({ data: body, failed: false, key });
      })
      .catch(() => {
        if (!cancelled) setState({ data: null, failed: true, key });
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId, key]);
  return state.key === key ? state : { data: null, failed: false };
}

/**
 * The sim-only sections of the player detail, split by tab of the shared Player Quick View: Overview (this week, rest of
 * season, owner, actions, game news), Outlook (this sim season's points and the rest-of-season band), Scouting
 * (generated rookies) and History (draft slot, moves, seasons; derived from the event log). Same section shell
 * (`pqv-stat-season`), same stat tiles (`StatGroup`) and the same weekly chart the real Player Quick View uses.
 */
export function simPqvSections(gameId: string, player: SimGamePlayer, detail: SimPlayerDetailState, actions?: ReactNode, seasonLabel?: string | null, real?: { playerId: string; asOf: number }): SimPqvSections {
  return {
    overview: <SimOverviewSection player={player} detail={detail} actions={actions} seasonLabel={seasonLabel} />,
    outlook: <SimOutlookSection player={player} detail={detail} seasonLabel={seasonLabel} />,
    scouting: detail.data?.scouting ? <SimScoutingSections profile={detail.data.scouting} /> : undefined,
    history: <SimPlayerHistory gameId={gameId} playerId={player.id} />,
    stats: real ? <SimRealHistory playerId={real.playerId} asOf={real.asOf} /> : undefined,
  };
}

function SimOverviewSection({ player, detail, actions, seasonLabel }: { player: SimGamePlayer; detail: SimPlayerDetailState; actions?: ReactNode; seasonLabel?: string | null }) {
  const body = detail.data;
  const status = simPlayerStatusLabel(player);
  const ros = body?.ros ?? null;
  const tiles = [
    { label: "This week", value: simProjText(player), note: status ? status.label : `${simFmtPts(player.floor)}-${simFmtPts(player.ceiling)}`, percentile: null },
    ros
      ? { label: "Rest of season", value: `${simFmtPts(ros.mean)} ppg`, note: `${simFmtPts(ros.floor)}-${simFmtPts(ros.ceiling)}`, percentile: null }
      : null,
    { label: seasonLabel || "This season", value: simFmtPts(player.season_points ?? 0), note: `${player.games ?? 0} games${player.ppg != null ? ` · ${simFmtPts(player.ppg)} ppg` : ""}`, percentile: null },
    {
      label: "Overall",
      value: player.overall != null ? String(player.overall) : "—",
      note: player.adp != null ? `ADP ${simFmtValue(player.adp)}` : "No ADP",
      percentile: null,
    },
  ].filter((t): t is { label: string; value: string; note: string; percentile: null } => t != null);

  return (
    <div className="flex flex-col gap-3 pt-2" data-testid="sim-player-overlay">
      <section className="pqv-stat-season" data-testid="sim-in-game">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3>In this game</h3>
          <span className="flex items-center gap-1 mb-2">
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {player.owner ? <SimToneBadge label={simOwnerLabel(player.owner)} tone={simOwnerTone(player.owner)} /> : null}
            {simRoleBadge(player) ? <SimToneBadge label={simRoleBadge(player)!.label} tone={simRoleBadge(player)!.tone} /> : null}
          </span>
        </div>
        <StatGroup title="In this game" items={tiles} hideTitle />
        {simIfStartsHint(player) ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="sim-if-starts">{simIfStartsHint(player)}</span>
        ) : null}
        {actions ? <div className="flex flex-wrap gap-2 pt-2">{actions}</div> : null}
      </section>
      {(body?.news ?? []).length > 0 ? (
        <section className="pqv-stat-season">
          <h3>Game news</h3>
          <ul className="flex flex-col gap-1.5">
            {body!.news!.map((n, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <ReviewGlyphChip glyph="stats" tone="accent" size={22} />
                <span className="min-w-0 flex-1">
                  <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>Week {n.week} · </span>
                  {n.text}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function SimOutlookSection({ player, detail, seasonLabel }: { player: SimGamePlayer; detail: SimPlayerDetailState; seasonLabel?: string | null }) {
  const body = detail.data;
  if (detail.failed) return <p className="pqv-status-text">Could not load the full outlook.</p>;
  if (!body) return <SkeletonRows count={2} />;
  const ros = body.ros ?? null;
  const flat = simProjectionIsFlat(body);
  const band = simProjectionBand(body);
  const actual = simActualPoints(body);
  const availability = ros ? simAvailabilityLine(ros) : null;
  if (!(actual.length > 0 || band || ros)) return <p className="pqv-status-text">No outlook yet.</p>;
  return (
    <section className="pqv-stat-season" data-testid="sim-weekly">
      <h3>Week by Week · {seasonLabel || "This sim season"}</h3>
      {actual.length > 0 || band ? (
        <WeeklyPointsPanel
          name={player.name}
          weeks={actual.map((a) => ({ week: a.week, fantasy_points_ppr: a.points, snap_share: null }))}
          season={0}
          projection={band}
          pointsLabel="pts"
          byeWeeks={ros?.bye_week ? [ros.bye_week] : []}
        />
      ) : null}
      {flat && ros ? (
        <p className="pqv-status-text" data-testid="sim-ros-line">
          <strong>{simRosLine(ros)}</strong>
          {availability ? <> &middot; {availability}</> : null}
        </p>
      ) : availability ? (
        <p className="pqv-status-text">{availability}</p>
      ) : null}
    </section>
  );
}

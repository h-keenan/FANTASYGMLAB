"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { SimDraftGlyph } from "@/components/SimDraftGlyphs";
import { SimPager, useSimDebounced, useSimWide } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { api } from "@/lib/api";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import { PlayerListRow } from "@/components/PlayerListRow";
import type { PlayerListDensity, PlayerListTag } from "@/lib/playerListRow";
import { simDraftMeta, simDraftRowChips, simListStats } from "@/lib/simDraft";
import { SIM_WINDOW_STEP, simWindow } from "@/lib/simLayout";
import {
  SIM_PAGE_SIZE,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simHeadshotId,
  simPageCount,
  simPlayerInitials,
  simPlayerIsGenerated,
  type SimGamePlayer,
  type SimPlayerSort,
  type SimPosFilter,
} from "@/lib/simGame";

const SORTS: { label: string; value: SimPlayerSort }[] = [
  { label: "ADP", value: "adp" },
  { label: "Proj", value: "projection" },
  { label: "Trade value", value: "value" },
];

/**
 * One sim player-list row: a thin mapping from a sim player onto the shared
 * PlayerListRow (docs/player-card.md, `list` variant). Draft Players/Board,
 * the rookie draft and the Players / Waivers tabs all render through it.
 * Bye is always shown (simDraftMeta), an injury is a chip + dot (never a
 * dimmed row), and every number is a labeled pill (simListStats).
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
  onGeneratedInfo,
  week = 0,
  drafted = false,
  tags,
  extra,
  density,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
  /** Opens the generated-class notice; shows a tiny "sim" dot on simulated rookies. */
  onGeneratedInfo?: () => void;
  /** Current game week (0 while drafting): decides which byes count as "soon". */
  week?: number;
  /** Optimistic: this player was just picked; the row flashes and slides out while the server confirms. */
  drafted?: boolean;
  /** Page-specific tags (at most two shown plus "+N"). */
  tags?: PlayerListTag[];
  extra?: ReactNode;
  density?: PlayerListDensity;
}) {
  const [chip] = simDraftRowChips(player);
  return (
    <PlayerListRow
      testId="draft-row"
      name={player.name}
      position={player.pos}
      headshotId={simHeadshotId(player)}
      fallbackLabel={simPlayerInitials(player)}
      meta={simDraftMeta(player, week)}
      chip={chip ? { label: chip.label, tone: chip.tone } : null}
      hurt={player.status === "out"}
      stats={simListStats(player)}
      tags={tags}
      extra={extra}
      actions={actions}
      density={density}
      done={drafted}
      onSimInfo={onGeneratedInfo && simPlayerIsGenerated(player) ? onGeneratedInfo : undefined}
      onOpen={onOpen ? () => onOpen(player) : undefined}
      openLabel={`${player.name}, ${player.pos}. Open player details`}
    />
  );
}

/**
 * The draft board: search, shared PillRow position + sort strips and a list of
 * SimDraftRow. Server-side paging/filtering through GET /players with the
 * status fixed to free agents (a draft pool), same contract as SimPlayerBrowser.
 */
export function SimDraftBoard({
  gameId,
  positions,
  onOpen,
  actions,
  refreshKey = 0,
  onItems,
  week = 0,
  draftedIds,
}: {
  gameId: string;
  /** Filter pills after "All" (simFilterPositionsFor): positions plus FLEX / SUPERFLEX. */
  positions: { label: string; value: SimPosFilter }[];
  week?: number;
  /** Players picked optimistically and still awaiting the server. */
  draftedIds?: string[];
  onOpen: (player: SimGamePlayer) => void;
  actions?: (player: SimGamePlayer) => ReactNode;
  refreshKey?: number;
  onItems?: (items: SimGamePlayer[]) => void;
}) {
  const [filter, dispatch] = useReducer(simFilterReducer, simDefaultFilter({ status: "available", sort: "adp" }));
  const [text, setText] = useState("");
  const debounced = useSimDebounced(text, PLAYER_SEARCH_DEBOUNCE_MS);
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
    dispatch({ type: "q", value: debounced });
  }, [debounced]);

  const query = useMemo(() => simFilterQuery({ ...filter, status: "available" }), [filter]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, query, refreshKey, attempt]);

  const rows = simWindow(items, wide ? items.length : visible);
  return (
    <section className="flex flex-col gap-3" aria-label="Players">
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-text-muted)" }}>
          <SimDraftGlyph name="search" />
        </span>
        <Input
          type="search"
          inputMode="search"
          placeholder="Search players or NFL teams"
          aria-label="Search players"
          value={text}
          onChange={(event) => setText(event.target.value)}
          className="w-full"
          style={{ paddingLeft: 36 }}
        />
      </div>
      <PillRow
        ariaLabel="Position filter"
        variant="scroll"
        options={[{ label: "All", value: "" }, ...positions]}
        active={filter.pos}
        onSelect={(value) => dispatch({ type: "pos", value: value as SimPosFilter | "" })}
      />
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold shrink-0" style={{ color: "var(--color-text-muted)" }}>Sort</span>
        <div className="min-w-0 flex-1">
          <PillRow ariaLabel="Sort players" variant="fill" options={SORTS} active={filter.sort} onSelect={(value) => dispatch({ type: "sort", value: value as SimPlayerSort })} />
        </div>
      </div>
      {state === "loading" && items.length === 0 ? (
        <SkeletonRows count={6} />
      ) : state === "error" ? (
        <EmptyState title="Could not load players" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => setAttempt((n) => n + 1)} />
      ) : items.length === 0 ? (
        <EmptyState title="No players left that match" subtitle="Try a different search or filter." />
      ) : (
        <div className="flex flex-col" style={{ opacity: state === "loading" ? 0.6 : 1 }}>
          <p className="text-xs pb-1" style={{ color: "var(--color-text-muted)" }} aria-live="polite">
            {total} player{total === 1 ? "" : "s"} left
          </p>
          {rows.shown.map((player) => (
            <SimDraftRow key={player.id} player={player} onOpen={onOpen} week={week} drafted={draftedIds?.includes(player.id)} actions={actions ? actions(player) : null} />
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

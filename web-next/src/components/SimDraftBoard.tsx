"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerNameText } from "@/components/PlayerNameText";
import { PositionBadge } from "@/components/PositionBadge";
import { SimDraftGlyph } from "@/components/SimDraftGlyphs";
import { SimPager, simToneColor, useSimDebounced, useSimWide } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import { positionColorVar } from "@/lib/playerPresentation";
import { simBoardEdge, simBoardProjection, simDraftRowChips } from "@/lib/simDraft";
import { SIM_WINDOW_STEP, simWindow } from "@/lib/simLayout";
import {
  SIM_PAGE_SIZE,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtPts,
  simFmtValue,
  simHeadshotId,
  simPageCount,
  simPlayerInitials,
  type SimGamePlayer,
  type SimPlayerSort,
  type SimPos,
} from "@/lib/simGame";

const SORTS: { label: string; value: SimPlayerSort }[] = [
  { label: "ADP", value: "adp" },
  { label: "Proj", value: "projection" },
  { label: "Value", value: "value" },
];

/** Proj / Value / ADP / Edge: the same four equal columns in the header and in every row, so numbers line up by construction. */
const STAT_GRID = "grid grid-cols-4 gap-1 text-center tabular-nums";

/**
 * One draft-board row, built for a 390px phone. Line 1: position badge, photo,
 * name with the NFL team chip and status chips inline, and the actions
 * (icon buttons) right-aligned. Line 2: Proj / Value / ADP / Edge in four
 * equal columns that match the header strip above the list.
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
}) {
  const colorVar = positionColorVar(player.pos);
  const chips = simDraftRowChips(player);
  const delta = simBoardEdge(player);
  const proj = simBoardProjection(player);
  const identity = (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className="flex shrink-0 justify-center" style={{ width: 38 }}>
        <PositionBadge position={player.pos} />
      </span>
      <span className="flex shrink-0 items-center justify-center" style={{ width: 32, height: 32 }}>
        <PlayerAvatar playerId={simHeadshotId(player)} size={32} fallbackLabel={simPlayerInitials(player)} />
      </span>
      <div className="flex min-w-0 flex-1 items-center gap-1.5">
        <PlayerNameText name={player.name} threshold={Infinity} className="min-w-0 truncate text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
        {player.team ? (
          <span
            className="shrink-0 text-[0.625rem] font-extrabold uppercase px-1.5 leading-4"
            style={{ borderRadius: "var(--radius-pill)", border: "var(--border-width-default) solid var(--color-border-strong)", color: "var(--color-text-secondary)" }}
            title="NFL team"
          >
            {player.team}
          </span>
        ) : null}
        {chips.map((chip) => (
          <ToneBadge key={chip.key} label={chip.label} color={simToneColor(chip.tone)} size="xs" />
        ))}
      </div>
    </div>
  );
  return (
    <div
      className="flex flex-col pb-0.5 pl-2 pr-1"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `4px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}`,
        opacity: proj.discounted ? 0.62 : 1,
      }}
      data-testid="draft-row"
      data-out={proj.discounted ? "true" : undefined}
    >
      <div className="flex items-center justify-between gap-1">
        {onOpen ? (
          <button
            type="button"
            onClick={() => onOpen(player)}
            className="flex min-w-0 flex-1 items-center text-left"
            style={{ minHeight: 40 }}
            aria-label={`${player.name}, ${player.pos}. Open player details`}
          >
            {identity}
          </button>
        ) : (
          identity
        )}
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
      <div className={`${STAT_GRID} pb-0.5 text-xs leading-4`} style={{ color: "var(--color-text-primary)" }}>
        <span title={proj.discounted ? "Per-game projection when healthy. Out or on bye this week." : undefined}>{simFmtPts(proj.value)}</span>
        <span>{simFmtValue(player.value)}</span>
        <span>{simFmtValue(player.adp)}</span>
        <span style={{ minHeight: 16 }}>
          {delta ? (
            <span className="font-extrabold" style={{ color: simToneColor(delta.tone) }} title={delta.tone === "success" ? "Steal: the market lets him fall past where our value ranks him" : "Reach: the market takes him earlier than our value ranks him"}>
              {delta.tone === "success" ? "▲" : "▼"} {delta.label.replace(/^[+-]/, "")}
            </span>
          ) : (
            <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>-</span>
          )}
        </span>
      </div>
    </div>
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
}: {
  gameId: string;
  positions: SimPos[];
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
        options={[{ label: "All", value: "" }, ...positions.map((pos) => ({ label: pos, value: pos }))]}
        active={filter.pos}
        onSelect={(value) => dispatch({ type: "pos", value: value as SimPos | "" })}
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
          <div className={`${STAT_GRID} pb-1 text-[0.625rem] font-extrabold uppercase`} style={{ color: "var(--color-text-muted)", paddingLeft: 4 + 8, paddingRight: 4 }} aria-hidden="true">
            <span>Proj</span>
            <span title="Model value on a 0-100 scale (the top player is 100), not the main app's raw market value">Value</span>
            <span title="Average draft position">ADP</span>
            <span title="Value rank vs ADP: green = steal, red = reach">Edge</span>
          </div>
          {rows.shown.map((player) => (
            <SimDraftRow key={player.id} player={player} onOpen={onOpen} actions={actions ? actions(player) : null} />
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

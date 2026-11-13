"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerNameText } from "@/components/PlayerNameText";
import { PositionBadge } from "@/components/PositionBadge";
import { SimGeneratedChip } from "@/components/SimGameDynastyParts";
import { SimDraftGlyph } from "@/components/SimDraftGlyphs";
import { SimPager, simToneColor, useSimDebounced, useSimWide } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import { positionColorVar } from "@/lib/playerPresentation";
import { simBoardEdge, simBoardProjection, simDraftMeta, simDraftRowChips } from "@/lib/simDraft";
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
  simPlayerIsGenerated,
  type SimGamePlayer,
  type SimGameTone,
  type SimPlayerSort,
  type SimPosFilter,
} from "@/lib/simGame";

const SORTS: { label: string; value: SimPlayerSort }[] = [
  { label: "ADP", value: "adp" },
  { label: "Proj", value: "projection" },
  { label: "Value", value: "value" },
];

/**
 * Column widths shared by the sticky header and every row's stat strip, so the
 * numbers sit exactly under their labels: Proj, Value, ADP, Edge.
 */
const STAT_COLS = [44, 40, 36, 44] as const;
const STAT_GRID_STYLE = { display: "grid", gridTemplateColumns: STAT_COLS.map((w) => `${w}px`).join(" "), justifyContent: "end", columnGap: 2 } as const;
const STAT_CLASS = "text-right tabular-nums";

/** Short muted text for the meta line; the bye turns warning-colored only when it is close. */
function metaColor(tone: SimGameTone | undefined): string {
  return tone ? simToneColor(tone) : "var(--color-text-muted)";
}

/**
 * One draft-board row, built for a 390px phone (~70px tall). Line 1: position
 * badge, 40px photo, the full name (one size smaller for long names before it
 * ever truncates), the red OUT chip only for injured players, and the actions.
 * Line 2 (muted): TEAM · Age · Bye N (the bye is always shown; see
 * simDraftMeta). Line 3: the stat strip, right-aligned in fixed-width columns
 * that match the sticky header. Edge is a small colored arrow only when the
 * gap is 3+ spots. An injured row is never dimmed: it is still draftable.
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
  onGeneratedInfo,
  week = 0,
  drafted = false,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
  /** Opens the generated-class notice; shows a small chip on simulated rookies. */
  onGeneratedInfo?: () => void;
  /** Current game week (0 while drafting): decides which byes count as "soon". */
  week?: number;
  /** Optimistic: this player was just picked; the row flashes and slides out while the server confirms. */
  drafted?: boolean;
}) {
  const colorVar = positionColorVar(player.pos);
  const chips = simDraftRowChips(player);
  const meta = simDraftMeta(player, week);
  const delta = simBoardEdge(player);
  const proj = simBoardProjection(player);
  const out = player.status === "out";
  const identity = (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className="flex shrink-0 justify-center" style={{ width: 34 }}>
        <PositionBadge position={player.pos} />
      </span>
      <span className="relative flex shrink-0 items-center justify-center" style={{ width: 40, height: 40 }}>
        <PlayerAvatar playerId={simHeadshotId(player)} size={40} fallbackLabel={simPlayerInitials(player)} />
        {out ? <span aria-hidden="true" className="absolute right-0 top-0 rounded-full" style={{ width: 9, height: 9, background: "var(--color-danger)", boxShadow: "0 0 0 2px var(--color-surface)" }} /> : null}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex min-w-0 items-center gap-1.5">
          <PlayerNameText
            name={player.name}
            threshold={Infinity}
            className={`min-w-0 truncate font-bold ${player.name.length > 18 ? "text-[0.8125rem]" : "text-sm"}`}
            style={{ color: "var(--color-text-primary)" }}
          />
          {chips.map((chip) => (
            <span key={chip.key} className="shrink-0">
              <ToneBadge label={chip.label.toUpperCase()} color={simToneColor(chip.tone)} size="xs" />
            </span>
          ))}
        </div>
        <p className="text-xs leading-4" style={{ color: "var(--color-text-muted)" }} data-testid="draft-meta">
          {meta.map((part, i) => (
            <span key={part.key}>
              {i > 0 ? " · " : ""}
              <span style={{ color: metaColor(part.tone), fontWeight: part.tone === "warning" ? 700 : undefined }} title={part.key === "bye" && part.tone === "warning" ? "Bye week is coming up soon" : undefined}>
                {part.text}
              </span>
            </span>
          ))}
        </p>
      </div>
    </div>
  );
  return (
    <div
      className={`flex flex-col py-1 pl-2 pr-1${drafted ? " sim-row-drafted" : ""}`}
      style={{
        borderBottom: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)",
        borderLeft: `3px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}`,
      }}
      data-testid="draft-row"
      data-out={out ? "true" : undefined}
      data-drafted={drafted ? "true" : undefined}
    >
      <div className="flex items-center justify-between gap-1.5">
        {onOpen ? (
          <button
            type="button"
            onClick={() => onOpen(player)}
            className="flex min-w-0 flex-1 items-center text-left"
            style={{ minHeight: 44 }}
            aria-label={`${player.name}, ${player.pos}. Open player details`}
          >
            {identity}
          </button>
        ) : (
          identity
        )}
        {drafted ? (
          <span className="shrink-0 pr-1 text-xs font-extrabold" style={{ color: "var(--color-accent)" }} role="status">
            Drafted ✓
          </span>
        ) : actions ? (
          <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-2 text-xs leading-4" style={{ color: "var(--color-text-primary)" }}>
        <span className="min-w-0">{onGeneratedInfo && simPlayerIsGenerated(player) ? <SimGeneratedChip label="Generated" onInfo={onGeneratedInfo} inRow /> : null}</span>
        <div style={STAT_GRID_STYLE}>
          <span className={STAT_CLASS} title={proj.discounted ? "Per-game projection (out this week)." : undefined}>{simFmtPts(proj.value)}</span>
          <span className={STAT_CLASS}>{simFmtValue(player.value)}</span>
          <span className={STAT_CLASS}>{simFmtValue(player.adp)}</span>
          <span className="flex justify-end" style={{ minHeight: 16 }}>
            {delta ? (
              <span
                className="rounded-full px-1.5 text-[0.6875rem] font-extrabold leading-4"
                style={{ color: simToneColor(delta.tone), background: `color-mix(in srgb, ${simToneColor(delta.tone)} 16%, transparent)` }}
                title={delta.tone === "success" ? "Steal: the market lets him fall past where our value ranks him" : "Reach: the market takes him earlier than our value ranks him"}
              >
                {delta.tone === "success" ? "▲" : "▼"}
                {delta.label.replace(/^[+-]/, "")}
              </span>
            ) : null}
          </span>
        </div>
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
          <div
            className="sticky z-10 flex justify-end pb-1 pr-1 text-[0.625rem] font-extrabold uppercase"
            style={{ top: 0, color: "var(--color-text-muted)", background: "var(--color-surface)" }}
            aria-hidden="true"
          >
            <div style={STAT_GRID_STYLE}>
              <span className={STAT_CLASS}>Proj</span>
              <span className={STAT_CLASS} title="Model value on a 0-100 scale (the top player is 100), not the main app's raw market value">Value</span>
              <span className={STAT_CLASS} title="Average draft position">ADP</span>
              <span className={STAT_CLASS} title="Value rank vs ADP: green = steal, red = reach">Edge</span>
            </div>
          </div>
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

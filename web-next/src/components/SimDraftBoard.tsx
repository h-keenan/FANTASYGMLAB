"use client";

import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerNameText } from "@/components/PlayerNameText";
import { PositionBadge } from "@/components/PositionBadge";
import { SimDraftGlyph } from "@/components/SimDraftGlyphs";
import { SimPager, simToneColor, useSimDebounced } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { PLAYER_SEARCH_DEBOUNCE_MS } from "@/lib/leaguePlayerSearch";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftAdpDelta, simDraftRowChips } from "@/lib/simDraft";
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

const STAT_CELL = "w-11 text-right tabular-nums";
const STAT_INDENT = 4 + 8 + 44 + 8 + 40 + 8;

/**
 * One draft-board row with a fixed grid: position-colored edge, a fixed badge
 * slot, a fixed avatar slot, then name / meta, with Proj / Value / ADP in
 * fixed-width right-aligned cells underneath so numbers line up row to row
 * and nothing shifts when a photo loads.
 */
export function SimDraftRow({
  player,
  pickNo,
  onOpen,
  actions,
}: {
  player: SimGamePlayer;
  pickNo: number;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
}) {
  const colorVar = positionColorVar(player.pos);
  const chips = simDraftRowChips(player);
  const delta = simDraftAdpDelta(player.adp, pickNo);
  const identity = (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className="flex shrink-0 justify-center" style={{ width: 44 }}>
        <PositionBadge position={player.pos} />
      </span>
      <span className="flex shrink-0 items-center justify-center" style={{ width: 40, height: 40 }}>
        <PlayerAvatar playerId={simHeadshotId(player)} size={40} fallbackLabel={simPlayerInitials(player)} />
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <PlayerNameText name={player.name} threshold={Infinity} className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
        <span className="flex flex-wrap items-center gap-1.5" style={{ minHeight: 16 }}>
          {player.team ? (
            <span
              className="text-[0.625rem] font-extrabold uppercase px-1.5 leading-4"
              style={{ borderRadius: "var(--radius-pill)", border: "var(--border-width-default) solid var(--color-border-strong)", color: "var(--color-text-secondary)" }}
              title="NFL team"
            >
              {player.team}
            </span>
          ) : null}
          {chips.map((chip) => (
            <ToneBadge key={chip.key} label={chip.label} color={simToneColor(chip.tone)} size="xs" />
          ))}
        </span>
      </div>
    </div>
  );
  return (
    <div
      className="flex flex-col gap-1 py-2 pl-2 pr-1"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `4px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}`,
      }}
      data-testid="draft-row"
    >
      <div className="flex items-center justify-between gap-2">
        {onOpen ? (
          <button
            type="button"
            onClick={() => onOpen(player)}
            className="flex min-w-0 flex-1 items-center text-left"
            style={{ minHeight: "var(--touch-target-min)" }}
            aria-label={`${player.name}, ${player.pos}. Open player details`}
          >
            {identity}
          </button>
        ) : (
          identity
        )}
        {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
      </div>
      <div className="flex items-center gap-2 text-xs" style={{ paddingLeft: STAT_INDENT - 4 - 8, color: "var(--color-text-primary)" }}>
        <span className={STAT_CELL}>{simFmtPts(player.projection)}</span>
        <span className={STAT_CELL}>{simFmtValue(player.value)}</span>
        <span className={STAT_CELL}>{simFmtValue(player.adp)}</span>
        <span className="w-11 text-right" style={{ minHeight: 16 }}>
          {delta ? (
            <span className="font-extrabold tabular-nums" style={{ color: simToneColor(delta.tone) }} title={delta.tone === "success" ? "Steal: past his ADP" : "Reach: ahead of his ADP"}>
              {delta.tone === "success" ? "▲" : "▼"} {delta.label.replace("-", "")}
            </span>
          ) : null}
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
  pickNo,
  onOpen,
  actions,
  refreshKey = 0,
  onItems,
}: {
  gameId: string;
  positions: SimPos[];
  /** Overall pick on the clock, for the ADP delta. */
  pickNo: number;
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
          <div className="flex items-center gap-2 pb-1 text-[0.625rem] font-extrabold uppercase" style={{ paddingLeft: STAT_INDENT - 4 - 8 + 4 + 8, color: "var(--color-text-muted)" }} aria-hidden="true">
            <span className={STAT_CELL}>Proj</span>
            <span className={STAT_CELL}>Value</span>
            <span className={STAT_CELL}>ADP</span>
            <span className="w-11 text-right">Edge</span>
          </div>
          {items.map((player) => (
            <SimDraftRow key={player.id} player={player} pickNo={pickNo} onOpen={onOpen} actions={actions ? actions(player) : null} />
          ))}
        </div>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: "page", value: page })} />
    </section>
  );
}

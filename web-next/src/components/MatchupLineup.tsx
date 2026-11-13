"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { EmptySlotCard, PlayerCard } from "@/components/PlayerCardKit";
import { PillRow } from "@/components/PillRow";
import { PositionBadge } from "@/components/PositionBadge";
import { TickNumber } from "@/components/TickNumber";
import { ToneBadge } from "@/components/ToneBadge";
import type { MatchupSide, MatchupWinProbability } from "@/lib/api";
import { changedPlayerIds, slotTotals, sortSlots, type SlotComparison, type SlotSortMode } from "@/lib/lineupSlots";
import { freshnessLabel } from "@/lib/liveScores";
import { formatSigned } from "@/lib/matchupPresentation";

/**
 * Two-sided, slot-by-slot lineup comparison: my player card and the
 * opponent's side by side on desktop, stacked on phones, with a center slot
 * label + mini win bar per row. Slot logic: lib/lineupSlots.ts (shared with
 * the app). Cards: components/PlayerCardKit.tsx (docs/player-card.md).
 */

/** Which players' live points just changed between two payloads (drives the card pulse). */
export function usePointPulses(slots: SlotComparison[]): Map<string, number> {
  const previous = useRef<SlotComparison[] | null>(null);
  const [pulses, setPulses] = useState<Map<string, number>>(() => new Map());
  useEffect(() => {
    const changed = changedPlayerIds(previous.current, slots);
    previous.current = slots;
    if (changed.size === 0) return;
    setPulses((current) => {
      const next = new Map(current);
      for (const id of changed) next.set(id, (next.get(id) ?? 0) + 1);
      return next;
    });
  }, [slots]);
  return pulses;
}

function leadTone(value: number): string {
  if (Math.abs(value) < 0.05) return "var(--color-text-muted)";
  return value > 0 ? "var(--color-success)" : "var(--color-danger)";
}

export function ComparisonHeader({
  mine,
  opponent,
  slots,
  odds,
  ageSeconds,
  live,
  sort,
  onSort,
}: {
  mine: MatchupSide;
  opponent: MatchupSide;
  slots: SlotComparison[];
  odds: MatchupWinProbability | null | undefined;
  ageSeconds?: number | null;
  live: boolean;
  sort: SlotSortMode;
  onSort: (mode: SlotSortMode) => void;
}) {
  const totals = slotTotals(slots);
  const showFinal = slots.some((slot) => slot.remaining >= 1);
  const pct = odds?.available === true && odds.probability != null ? Math.round(odds.probability * 100) : null;
  const leads = slots.filter((slot) => slot.leader === "mine").length;
  const trails = slots.filter((slot) => slot.leader === "opponent").length;
  const hasDeciding = slots.some((slot) => slot.decides);
  return (
    <div className="flex flex-col gap-2" data-testid="comparison-header">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        <div className="flex flex-col min-w-0">
          <span className="text-[11px] font-bold truncate" style={{ color: "var(--color-accent)" }}>
            {mine.team_name || "You"}
          </span>
          <TickNumber value={totals.mineNow} testId="total-mine" className="text-2xl font-extrabold leading-none" style={{ color: "var(--color-text-primary)" }} />
          {showFinal ? (
            <span className="text-[11px] tabular-nums" style={{ color: "var(--color-text-secondary)" }} data-testid="final-mine">
              Proj final {totals.mineFinal.toFixed(1)}
            </span>
          ) : null}
        </div>
        <div className="flex flex-col items-center gap-1">
          {pct != null ? (
            <span className="text-xs font-extrabold tabular-nums" style={{ color: pct >= 50 ? "var(--color-success)" : "var(--color-danger)" }} data-testid="header-winprob">
              {pct}% win
            </span>
          ) : null}
          <ToneBadge
            label={Math.abs(totals.marginNow) < 0.05 ? "Even" : formatSigned(totals.marginNow)}
            color={leadTone(totals.marginNow)}
            title="Your margin on the lineups' current totals"
          />
        </div>
        <div className="flex flex-col items-end min-w-0 text-right">
          <span className="text-[11px] font-bold truncate max-w-full" style={{ color: "var(--color-text-primary)" }}>
            {opponent.team_name || "Opponent"}
          </span>
          <TickNumber value={totals.opponentNow} testId="total-opponent" className="text-2xl font-extrabold leading-none" style={{ color: "var(--color-text-primary)" }} />
          {showFinal ? (
            <span className="text-[11px] tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
              Proj final {totals.opponentFinal.toFixed(1)}
            </span>
          ) : null}
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 flex-wrap text-[11px]" style={{ color: "var(--color-text-muted)" }}>
        <span>
          You lead {leads} slot{leads === 1 ? "" : "s"}, trail {trails}
          {ageSeconds != null ? (
            <>
              {" · "}
              <span aria-live="polite" data-testid="header-asof">
                {freshnessLabel(ageSeconds)}
              </span>
            </>
          ) : live ? " · Live" : null}
        </span>
        {hasDeciding ? (
          <PillRow
            options={[
              { label: "Lineup order", value: "lineup" },
              { label: "Deciding first", value: "decisive" },
            ]}
            active={sort}
            onSelect={(value) => onSort(value as SlotSortMode)}
          />
        ) : null}
      </div>
    </div>
  );
}

function SlotCenter({ slot }: { slot: SlotComparison }) {
  const share = slot.barShare;
  const lead = slot.leader === "mine" ? slot.margin : slot.leader === "opponent" ? -slot.margin : 0;
  return (
    <div className="flex sm:flex-col items-center justify-center gap-2 sm:gap-1.5 px-1 py-0.5" data-testid="slot-center">
      <PositionBadge position={slot.slot} label={slot.label} size="md" />
      <span
        className="winprob-bar-track flex-1 sm:flex-none sm:w-full"
        role="img"
        aria-label={
          share == null
            ? `${slot.label}: no comparison yet`
            : `${slot.label}: you ${Math.round(share)}% of this slot, opponent ${100 - Math.round(share)}%`
        }
        data-testid="slot-bar"
      >
        <span className="winprob-bar-fill" style={{ width: `${share ?? 50}%`, opacity: share == null ? 0.25 : 1 }} aria-hidden="true" />
      </span>
      <span
        className="text-[11px] font-extrabold tabular-nums w-12 sm:w-auto text-right sm:text-center"
        style={{ color: leadTone(lead) }}
        data-testid="slot-lead"
      >
        {slot.leader == null ? "—" : slot.leader === "tie" ? "Even" : formatSigned(lead)}
      </span>
      {slot.decides ? <ToneBadge size="xs" label="Decides" color="var(--color-warning)" testId="slot-decides" title="One of the closest slots still in play" /> : null}
    </div>
  );
}

export function SlotRow({
  slot,
  pulses,
  onEditMine,
}: {
  slot: SlotComparison;
  pulses: Map<string, number>;
  /** Planner mode: swap handler for my slot. */
  onEditMine?: () => void;
}) {
  const emphasis = (side: "mine" | "opponent") =>
    slot.leader == null || slot.leader === "tie" ? "even" : slot.leader === side ? "win" : "lose";
  const cell = (side: "mine" | "opponent") => {
    const value = side === "mine" ? slot.mine : slot.opponent;
    if (value.kind === "none") return <div />;
    if (value.kind === "empty") return <EmptySlotCard onEdit={side === "mine" ? onEditMine : undefined} />;
    const card = value.card;
    return (
      <PlayerCard
        variant="matchup"
        model={card}
        mirror={side === "opponent"}
        sideTag={side === "mine" ? "you" : "opp"}
        emphasis={emphasis(side)}
        pulseKey={card.playerId ? (pulses.get(card.playerId) ?? 0) : 0}
        identity={{ ...value.source, sourceLabel: "Matchup" }}
        onEdit={side === "mine" ? onEditMine : undefined}
      />
    );
  };
  return (
    <li
      className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_6.5rem_minmax(0,1fr)] gap-1.5 sm:gap-2 items-stretch slot-row"
      data-decides={slot.decides ? "true" : undefined}
      data-testid="slot-row"
      data-slot={slot.label}
    >
      {cell("mine")}
      <SlotCenter slot={slot} />
      {cell("opponent")}
    </li>
  );
}

export function SlotList({
  slots,
  sort,
  planEditIndex,
}: {
  slots: SlotComparison[];
  sort: SlotSortMode;
  /** Planner mode: maps a slot to a handler that opens the swap sheet (undefined: not editable). */
  planEditIndex?: (slot: SlotComparison) => (() => void) | undefined;
}) {
  const pulses = usePointPulses(slots);
  const ordered = useMemo(() => sortSlots(slots, sort), [slots, sort]);
  return (
    <ol className="flex flex-col gap-2.5 list-none p-0 m-0" aria-label="Lineup comparison by slot">
      {ordered.map((slot) => (
        <SlotRow key={slot.key} slot={slot} pulses={pulses} onEditMine={planEditIndex?.(slot)} />
      ))}
    </ol>
  );
}

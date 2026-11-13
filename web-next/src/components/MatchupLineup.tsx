"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { EmptySlotCard, PlayerCard } from "@/components/PlayerCardKit";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerName } from "@/components/PlayerName";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { useIsPhone } from "@/components/useIsPhone";
import {
  headlinePoints,
  playerStatusChips,
  trendVsProjection,
  type ChipTone,
  type PlayerCardModel,
} from "@/lib/playerCard";
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

type GlyphKind = "live" | "upcoming" | "final" | "bye" | "out";

/** Status as color AND shape (never color alone): live = filled dot, upcoming = hollow ring, final = check, bye = dash, out = x. */
export function StatusGlyph({ kind, tone }: { kind: GlyphKind; tone: ChipTone }) {
  const color = DOT_COLOR[tone];
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" style={{ color, flexShrink: 0 }} data-glyph={kind}>
      {kind === "live" ? <circle cx="5" cy="5" r="3.2" fill="currentColor" className="motion-safe:animate-pulse" /> : null}
      {kind === "upcoming" ? <circle cx="5" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.6" /> : null}
      {kind === "final" ? <path d="M1.8 5.2 4.2 7.6 8.4 2.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /> : null}
      {kind === "bye" ? <path d="M2 5h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /> : null}
      {kind === "out" ? <path d="M2.5 2.5l5 5M7.5 2.5l-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /> : null}
    </svg>
  );
}

const DOT_COLOR: Record<ChipTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

/** One side of a phone row: photo, truncated name, status dot, points + tiny projected-final arrow. */
function CompactSide({
  cell,
  mirror,
  emphasis,
  pulseKey,
  onEdit,
}: {
  cell: SlotComparison["mine"];
  mirror: boolean;
  emphasis: "win" | "lose" | "even";
  pulseKey: number;
  onEdit?: () => void;
}) {
  if (cell.kind === "none") return <div />;
  if (cell.kind === "empty") {
    return (
      <div className="text-[11px] italic px-1" style={{ color: onEdit ? "var(--color-accent)" : "var(--color-text-muted)" }}>
        {onEdit ? <button type="button" onClick={onEdit}>Empty, tap to fill</button> : "Empty slot"}
      </div>
    );
  }
  const card: PlayerCardModel = cell.card;
  const head = headlinePoints(card);
  const trend = trendVsProjection(card);
  const chips = playerStatusChips(card);
  const primary = chips[0];
  const flag = chips.find((chip) => chip.kind === "questionable" || chip.kind === "doubtful");
  const dir = mirror ? " flex-row-reverse text-right" : "";
  const body = (
    <>
      <PlayerAvatar playerId={card.playerId} tier={card.tier} size={36} fallbackLabel={card.team} />
      <span className={`flex flex-col min-w-0 flex-1 gap-0.5${mirror ? " items-end" : ""}`}>
        <PlayerName name={card.name} className="text-[12px] font-bold leading-tight w-full" style={{ color: "var(--color-text-primary)" }} />
        <span className={`flex items-center gap-1 text-[10px] font-extrabold uppercase leading-none${mirror ? " flex-row-reverse" : ""}`} style={{ letterSpacing: "var(--letter-spacing-badge)" }}>
          {primary ? (
            <span className="inline-flex items-center" data-testid={`compact-status-${primary.kind}`} title={primary.label}>
              <StatusGlyph kind={primary.kind as GlyphKind} tone={primary.tone} />
              <span className="sr-only">{primary.label}</span>
            </span>
          ) : null}
          {flag ? <span style={{ color: DOT_COLOR[flag.tone] }}>{flag.kind === "doubtful" ? "D" : "Q"}</span> : null}
        </span>
        <span className={`flex items-baseline gap-1.5${mirror ? " flex-row-reverse" : ""}`}>
          {head.value != null ? (
            <TickNumber
              value={head.value}
              className="text-[16px] font-extrabold leading-none"
              style={{ color: emphasis === "lose" ? "var(--color-text-muted)" : head.kind === "pts" ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
            />
          ) : (
            <span className="text-[16px] font-extrabold leading-none" style={{ color: "var(--color-text-muted)" }}>
              {card.bye || card.out ? "0.0" : "—"}
            </span>
          )}
          {card.projectedFinal != null ? (
            <span
              className="text-[10px] font-bold tabular-nums"
              style={{ color: trend ? (trend.dir === "up" ? "var(--color-success)" : trend.dir === "down" ? "var(--color-danger)" : "var(--color-text-muted)") : "var(--color-text-secondary)" }}
              title="Projected final"
            >
              {trend ? (trend.dir === "up" ? "▲" : trend.dir === "down" ? "▼" : "–") : ""}
              {card.projectedFinal.toFixed(1)}
            </span>
          ) : head.kind === "proj" ? (
            <span className="text-[10px] font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>proj</span>
          ) : null}
        </span>
      </span>
    </>
  );
  const cls = `flex items-center gap-1.5 min-w-0 w-full${dir}`;
  return (
    <div className="relative min-w-0 rounded-lg px-0.5 py-1" style={emphasis === "win" ? { background: "color-mix(in srgb, var(--color-accent) 9%, transparent)" } : undefined}>
      {pulseKey > 0 ? <span key={pulseKey} className="player-card-pulse" aria-hidden="true" /> : null}
      {onEdit ? (
        <button type="button" onClick={onEdit} aria-label={`Swap ${card.name}`} className={`${cls} text-left`}>
          {body}
        </button>
      ) : (
        <PlayerIdentityTrigger identity={{ ...cell.source, sourceLabel: "Matchup" }} className={cls}>
          {body}
        </PlayerIdentityTrigger>
      )}
    </div>
  );
}

/** Phone row: [my player] [slot label + lead bar + margin, tap to expand] [opponent mirrored]. */
export function CompactSlotRow({
  slot,
  pulses,
  onEditMine,
  open,
  onToggle,
}: {
  slot: SlotComparison;
  pulses: Map<string, number>;
  onEditMine?: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  const emphasis = (side: "mine" | "opponent") =>
    slot.leader == null || slot.leader === "tie" ? "even" : slot.leader === side ? "win" : "lose";
  const pulse = (cell: SlotComparison["mine"]) => (cell.kind === "player" && cell.card.playerId ? (pulses.get(cell.card.playerId) ?? 0) : 0);
  const lead = slot.leader === "mine" ? slot.margin : slot.leader === "opponent" ? -slot.margin : 0;
  const share = slot.barShare;
  return (
    <li className="flex flex-col slot-row" data-decides={slot.decides ? "true" : undefined} data-testid="slot-row" data-slot={slot.label} data-compact="true">
      <div className="grid grid-cols-[minmax(0,1fr)_3.2rem_minmax(0,1fr)] items-center gap-1">
        <CompactSide cell={slot.mine} mirror={false} emphasis={emphasis("mine")} pulseKey={pulse(slot.mine)} onEdit={onEditMine} />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={`${slot.label} details`}
          className="flex flex-col items-center gap-1 py-0.5"
          data-testid="slot-center"
        >
          <PositionBadge position={slot.slot} label={slot.label} />
          <span className="winprob-bar-track w-full" role="img" data-testid="slot-bar" aria-label={share == null ? `${slot.label}: no comparison yet` : `${slot.label}: you ${Math.round(share)}%`}>
            <span className="winprob-bar-fill" style={{ width: `${share ?? 50}%`, opacity: share == null ? 0.25 : 1 }} aria-hidden="true" />
          </span>
          <span className="flex items-center gap-0.5 text-[11px] font-extrabold tabular-nums leading-none" style={{ color: leadTone(lead) }} data-testid="slot-lead">
            {slot.leader == null ? "—" : slot.leader === "tie" ? "Even" : formatSigned(lead)}
            <svg width="8" height="8" viewBox="0 0 10 10" aria-hidden="true" style={{ color: "var(--color-text-muted)", transform: open ? "rotate(180deg)" : undefined }}>
              <path d="M1.5 3.5 5 7l3.5-3.5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </button>
        <CompactSide cell={slot.opponent} mirror emphasis={emphasis("opponent")} pulseKey={pulse(slot.opponent)} />
      </div>
      {open ? (
        <div className="flex flex-col gap-1.5 pt-1.5 pb-1" data-testid="slot-expanded">
          {([["mine", slot.mine], ["opponent", slot.opponent]] as const).map(([side, cell]) =>
            cell.kind === "player" ? (
              <PlayerCard
                key={side}
                variant="matchup"
                model={cell.card}
                emphasis={emphasis(side)}
                sideTag={side === "mine" ? "you" : "opp"}
                identity={{ ...cell.source, sourceLabel: "Matchup" }}
              />
            ) : null,
          )}
        </div>
      ) : null}
    </li>
  );
}

function PhoneLegend() {
  const items: [GlyphKind, ChipTone, string][] = [
    ["live", "success", "Live"],
    ["upcoming", "accent", "Upcoming"],
    ["final", "muted", "Final"],
    ["bye", "warning", "Bye"],
    ["out", "danger", "Out"],
  ];
  return (
    <p className="m-0 flex items-center gap-x-3 gap-y-1 flex-wrap text-[10px] font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }} data-testid="slot-legend">
      {items.map(([kind, tone, label]) => (
        <span key={label} className="inline-flex items-center gap-1">
          <StatusGlyph kind={kind} tone={tone} />
          {label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1">
        <span aria-hidden="true" className="inline-block rounded-sm" style={{ width: 10, height: 6, boxShadow: "0 0 0 1px var(--color-warning)" }} />
        Decides
      </span>
      <span>Tap middle to expand</span>
    </p>
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
  const phone = useIsPhone();
  const [openKey, setOpenKey] = useState<string | null>(null);
  if (phone) {
    return (
      <div className="flex flex-col gap-2">
        <PhoneLegend />
        <ol className="flex flex-col gap-1 list-none p-0 m-0" aria-label="Lineup comparison by slot">
          {ordered.map((slot) => (
            <CompactSlotRow
              key={slot.key}
              slot={slot}
              pulses={pulses}
              onEditMine={planEditIndex?.(slot)}
              open={openKey === slot.key}
              onToggle={() => setOpenKey((current) => (current === slot.key ? null : slot.key))}
            />
          ))}
        </ol>
      </div>
    );
  }
  return (
    <ol className="flex flex-col gap-2.5 list-none p-0 m-0" aria-label="Lineup comparison by slot">
      {ordered.map((slot) => (
        <SlotRow key={slot.key} slot={slot} pulses={pulses} onEditMine={planEditIndex?.(slot)} />
      ))}
    </ol>
  );
}

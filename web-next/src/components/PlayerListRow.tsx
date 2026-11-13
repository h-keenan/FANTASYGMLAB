"use client";

import type { CSSProperties, ReactNode } from "react";

import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { TapForWhy } from "@/components/ui/TapForWhy";
import type { ChipTone } from "@/lib/playerCard";
import type { WhyMetricId } from "@/lib/tapForWhyContent";
import {
  PLAYER_LIST_DENSITY,
  PLAYER_LIST_LONG_NAME,
  PLAYER_LIST_ALIGNED_WIDTH,
  playerListSlotWidth,
  PLAYER_LIST_STAT_ORDER,
  PLAYER_LIST_STAT_WIDTH,
  limitPlayerListTags,
  orderPlayerListStats,
  type PlayerListDensity,
  type PlayerListMetaPart,
  type PlayerListStat,
  type PlayerListTag,
} from "@/lib/playerListRow";
import { positionColorVar } from "@/lib/playerPresentation";

/**
 * THE player-list row: the `list` variant of the player card system
 * (docs/player-card.md). Props-driven; pages pass their own tags, stats and
 * actions, the look never changes.
 *
 *  - Line 1: position badge, photo, name (a size smaller before it truncates),
 *    one status chip only when it matters (OUT, Q, BYE soon, NEW, ROOKIE).
 *  - Line 2 (muted): TEAM · Age · Bye N. Generated players get a small info glyph by the actions.
 *  - Line 3: page tags (at most 2 + "+N") on the left, LABELED stat pills
 *    (PROJ / OVR / ADP / EDGE; OVR is the shared overall gauge) in fixed-width slots on the right. A number never
 *    appears without its caption.
 *  - Actions slot (compact icon buttons) and tap-row-to-open.
 *
 * Never dims a row for an injury: the chip and a red avatar dot say it.
 */

const TONE_COLOR: Record<ChipTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

export interface PlayerListRowProps {
  name: string;
  position: string | null;
  headshotId?: string | null;
  fallbackLabel?: string;
  /** Muted second line. */
  meta?: PlayerListMetaPart[];
  /** The single status chip that matters, if any. */
  chip?: { label: string; tone: ChipTone } | null;
  /** Show the red "hurt" dot on the photo. */
  hurt?: boolean;
  stats?: PlayerListStat[];
  /** Page-specific tags; at most two are shown plus "+N". */
  tags?: PlayerListTag[];
  /** Free content under the meta line (e.g. an owner badge). */
  extra?: ReactNode;
  /** Primary action slot: compact 36-44px icon buttons. */
  actions?: ReactNode;
  /** Tap the row to open (PQV or the game's own sheet). */
  onOpen?: () => void;
  openLabel?: string;
  density?: PlayerListDensity;
  /** Optimistic: just picked / added; flashes and slides out. */
  done?: boolean;
  doneLabel?: string;
  /** Generated (simulated) player: shows a small info glyph that opens the explainer (the class chip lives on the list header). */
  onSimInfo?: () => void;
  testId?: string;
  selected?: boolean;
  /** Every row of this list shows the same stats: anchor the stat block left at a fixed width so columns line up even when only some rows have an EDGE. */
  alignColumns?: boolean;
}

function StatPill({ stat }: { stat: PlayerListStat }) {
  // The player's Overall is the shared OVR gauge (same ring, thresholds and colors as the Quick View hero),
  // explained on tap with the registry's OVR copy. Never a plain number pill.
  if (stat.rating != null) {
    return (
      <TapForWhy metric="ovr" spoken={`Overall ${stat.rating}`}>
        <span className="inline-flex items-center gap-1" data-stat={stat.key}>
          <span className="text-[0.6875rem] font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
            {stat.label}
          </span>
          <OvrGauge rating={stat.rating} size="sm" />
        </span>
      </TapForWhy>
    );
  }
  const pill = (
    <span
      className="inline-flex items-baseline justify-end gap-1 rounded-full px-1.5 leading-4 tabular-nums"
      style={{ background: "var(--glass-input-bg)" }}
      data-stat={stat.key}
    >
      <span className="text-[0.6875rem] font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
        {stat.label}
      </span>
      <span className="text-xs font-bold" style={{ color: stat.tone ? TONE_COLOR[stat.tone] : "var(--color-text-primary)" }}>
        {stat.value}
      </span>
    </span>
  );
  return stat.why ? (
    <TapForWhy metric={stat.why as WhyMetricId} spoken={`${stat.label} ${stat.value}`}>
      {pill}
    </TapForWhy>
  ) : (
    pill
  );
}

export function PlayerListRow({
  name,
  position,
  headshotId,
  fallbackLabel,
  meta = [],
  chip,
  hurt = false,
  stats = [],
  tags = [],
  extra,
  actions,
  onOpen,
  openLabel,
  density = "comfortable",
  done = false,
  doneLabel = "Drafted ✓",
  onSimInfo,
  testId = "player-list-row",
  selected = false,
  alignColumns = false,
}: PlayerListRowProps) {
  const dims = PLAYER_LIST_DENSITY[density];
  const colorVar = positionColorVar(position);
  const slots = orderPlayerListStats(stats);
  const { shown, extra: moreTags } = limitPlayerListTags(tags);
  const hasLine3 = slots.length > 0 || shown.length > 0;
  const identity = (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <span className="flex shrink-0 justify-center" style={{ width: 34 }}>
        <PositionBadge position={position} />
      </span>
      <span className="relative flex shrink-0 items-center justify-center" style={{ width: dims.avatar, height: dims.avatar }}>
        <PlayerAvatar playerId={headshotId ?? null} size={dims.avatar} fallbackLabel={fallbackLabel ?? name.slice(0, 2)} />
        {hurt ? <span aria-hidden="true" className="absolute right-0 top-0 rounded-full" style={{ width: 9, height: 9, background: "var(--color-danger)", boxShadow: "0 0 0 2px var(--color-surface)" }} /> : null}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex min-w-0 items-center gap-1.5">
          <PlayerName
            name={name}
            className={`min-w-0 truncate font-bold ${name.length > PLAYER_LIST_LONG_NAME ? "text-[0.8125rem]" : "text-sm"}`}
            style={{ color: "var(--color-text-primary)" }}
          />
          {chip ? (
            <span className="shrink-0">
              <ToneBadge label={chip.label.toUpperCase()} color={TONE_COLOR[chip.tone]} size="xs" />
            </span>
          ) : null}
        </div>
        {meta.length > 0 ? (
          <p className="text-xs leading-4" style={{ color: "var(--color-text-muted)" }} data-testid="list-meta">
            {meta.map((part, i) => (
              <span key={part.key}>
                {i > 0 ? " · " : ""}
                <span style={{ color: part.tone ? TONE_COLOR[part.tone] : undefined, fontWeight: part.tone === "warning" ? 700 : undefined }}>{part.text}</span>
              </span>
            ))}
          </p>
        ) : null}
        {extra}
      </div>
    </div>
  );
  return (
    <div
      className={`flex flex-col py-1 pl-2 pr-1${done ? " sim-row-drafted" : ""}`}
      style={
        {
          borderBottom: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)",
          borderLeft: `3px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}`,
          background: selected ? "var(--color-accent-soft)" : undefined,
        } as CSSProperties
      }
      data-testid={testId}
      data-out={hurt ? "true" : undefined}
      data-drafted={done ? "true" : undefined}
    >
      <div className="flex items-center justify-between gap-1.5">
        {onOpen ? (
          <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center text-left" style={{ minHeight: dims.minHeight }} aria-label={openLabel ?? `${name}${position ? `, ${position}` : ""}. Open player details`}>
            {identity}
          </button>
        ) : (
          identity
        )}
        {onSimInfo && !done ? (
          <button
            type="button"
            onClick={onSimInfo}
            className="inline-flex shrink-0 items-center justify-center"
            style={{ color: "var(--color-accent)", width: 28, height: 28 }}
            aria-label="About simulated players"
            title="Simulated player: this class is generated, not real"
          >
            <span aria-hidden="true" className="text-[0.6875rem] font-black leading-none">ⓘ</span>
          </button>
        ) : null}
        {done ? (
          <span className="shrink-0 pr-1 text-xs font-extrabold" style={{ color: "var(--color-accent)" }} role="status">
            {doneLabel}
          </span>
        ) : actions ? (
          <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
        ) : null}
      </div>
      {hasLine3 ? (
        <div className="flex items-center justify-between gap-2 pb-0.5">
          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden whitespace-nowrap" data-testid="list-tags">
            {shown.map((tag) => (
              <ToneBadge key={tag.key} label={tag.label} color={tag.tone ? TONE_COLOR[tag.tone] : "var(--color-text-secondary)"} size="xs" />
            ))}
            {moreTags > 0 ? (
              <span className="text-[0.625rem] font-bold" style={{ color: "var(--color-text-muted)" }}>
                +{moreTags}
              </span>
            ) : null}
          </div>
          <div className={`flex shrink-0 items-center gap-0.5 ${alignColumns ? "justify-start" : "justify-end"}`} style={alignColumns ? { minWidth: PLAYER_LIST_ALIGNED_WIDTH } : undefined} data-testid="list-stats">
            {slots.map((stat, i) =>
              stat ? (
                <span key={stat.key} className="flex justify-end" style={{ minWidth: PLAYER_LIST_STAT_WIDTH[stat.key] ?? 66 }}>
                  <StatPill stat={stat} />
                </span>
              ) : (
                <span key={`empty-${i}`} aria-hidden="true" style={{ minWidth: playerListSlotWidth(i, alignColumns) }} />
              ),
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

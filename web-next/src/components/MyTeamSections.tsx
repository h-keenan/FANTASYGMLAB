"use client";

import { useId, useState, type ReactNode } from "react";

import { HighlightTarget } from "@/components/HighlightTarget";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerRow } from "@/components/PlayerRow";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueStat } from "@/components/ValueStat";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import type { KeeperPlayerInfo, LineupPlayer } from "@/lib/api";
import type { CompositionSegment, TeamAnalysisRow } from "@/lib/myTeamAnalysis";
import { lineupIneligibleTag } from "@/lib/myTeamPresentation";

const TONE_VAR: Record<TeamAnalysisRow["tone"], string> = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  information: "var(--color-information)",
};

function Chevron({ open = false }: { open?: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
      style={{ transform: open ? "rotate(90deg)" : undefined, color: "var(--color-text-muted)" }}
    >
      <path d="M6 3l5 5-5 5" />
    </svg>
  );
}

/** One row per position room: status dot + short status; tap for the full
 * sentence. */
export function TeamAnalysisList({ rows }: { rows: TeamAnalysisRow[] }) {
  const [openPosition, setOpenPosition] = useState<string | null>(null);
  const baseId = useId();
  return (
    <div className="glass-surface flex flex-col">
      {rows.map((row, index) => {
        const open = openPosition === row.position;
        const panelId = `${baseId}-${row.position}`;
        return (
          <div
            key={row.position}
            style={index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined}
          >
            <button
              type="button"
              onClick={() => setOpenPosition(open ? null : row.position)}
              aria-expanded={open}
              aria-controls={panelId}
              className="flex w-full items-center gap-3 px-3 py-3 text-left"
              style={{ background: "none", border: "none", cursor: "pointer" }}
            >
              <PositionBadge position={row.position} />
              <span
                aria-hidden="true"
                className="shrink-0"
                style={{ width: 10, height: 10, borderRadius: 999, background: TONE_VAR[row.tone] }}
              />
              <span className="flex-1 text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                {row.status}
              </span>
              <Chevron open={open} />
            </button>
            {open ? (
              <p id={panelId} className="px-3 pb-3 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {row.body}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function surplusText(info: KeeperPlayerInfo | undefined): string | null {
  if (!info || info.surplus == null || info.cost_round == null) return null;
  return `${info.kept_round ? "Kept" : "Est."} R${info.cost_round} · ${info.surplus > 0 ? "+" : ""}${info.surplus}`;
}

function badgeLabel(player: LineupPlayer, showSlot: boolean): string | null | undefined {
  if (!showSlot || !player.slot || player.slot === "BENCH") return player.position;
  return player.slot === "SUPER_FLEX" ? "SF" : player.slot.replace("_", " ");
}

function RosterRow({
  player,
  keeper,
  muted,
  showSlot,
}: {
  player: LineupPlayer;
  keeper?: KeeperPlayerInfo;
  muted: boolean;
  showSlot: boolean;
}) {
  const { openPlayer } = usePlayerQuickView();
  const identity = { ...player, sourceLabel: "My Team" };
  const ineligibleTag = lineupIneligibleTag(player);
  const surplus = surplusText(keeper);
  return (
    <PlayerRow
      bordered
      identity={identity}
      playerId={player.player_id}
      name={player.name || "Unknown player"}
      position={badgeLabel(player, showSlot)}
      tier={player.tier}
      injuryStatus={player.injury_label}
      muted={muted}
      className="flex-1 min-w-0"
      trailing={
        <>
          <OvrGauge rating={player.overall_rating} size="sm" />
          <ValueStat value={player.score != null ? Math.round(player.score) : "—"} />
          <button
            type="button"
            aria-label={`Open ${player.name || "player"}`}
            onClick={() => openPlayer(identity)}
            className="inline-flex items-center justify-center -my-3 min-w-[var(--touch-target-min)] min-h-[var(--touch-target-min)]"
            style={{ background: "none", border: "none", cursor: "pointer" }}
          >
            <Chevron />
          </button>
        </>
      }
    >
      {player.team || "FA"} · {player.position}
      {ineligibleTag ? (
        <span className="font-bold" style={{ color: "var(--color-warning)" }}>
          {` · ${ineligibleTag}`}
        </span>
      ) : null}
      {keeper?.is_keeper ? (
        <span className="ml-1">
          <ToneBadge label="Keeper" color="var(--color-information)" />
        </span>
      ) : null}
      {surplus ? ` · ${surplus}` : ""}
    </PlayerRow>
  );
}

export interface RosterTab {
  value: "starters" | "bench" | "ir" | "taxi" | "idp";
  label: string;
  players: LineupPlayer[];
  /** Slot labels (FLEX, SF) replace the position badge on this tab. */
  showSlot?: boolean;
  muted?: boolean;
}

export function RosterTabs({
  tabs,
  keepers,
  highlightPlayerId,
  emptyText,
  topNote,
}: {
  tabs: RosterTab[];
  keepers?: Record<string, KeeperPlayerInfo> | null;
  highlightPlayerId?: string;
  emptyText: string;
  topNote?: ReactNode;
}) {
  const initial =
    tabs.find((tab) => highlightPlayerId && tab.players.some((p) => p.player_id === highlightPlayerId))?.value ??
    tabs[0]?.value;
  const [active, setActive] = useState<string>(initial ?? "starters");
  const current = tabs.find((tab) => tab.value === active) ?? tabs[0];
  return (
    <div className="flex flex-col gap-3">
      <PillRow
        options={tabs.map((tab) => ({ label: tab.label, value: tab.value }))}
        active={current?.value ?? ""}
        onSelect={setActive}
        fullWidth
      />
      {topNote}
      {!current || current.players.length === 0 ? (
        <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-muted)" }}>
          {emptyText}
        </p>
      ) : (
        <div className="glass-surface flex flex-col px-3">
          {current.players.map((player) => (
            <HighlightTarget key={player.player_id} active={player.player_id === highlightPlayerId}>
              <RosterRow
                player={player}
                keeper={keepers?.[player.player_id]}
                muted={current.muted ?? false}
                showSlot={current.showSlot ?? false}
              />
            </HighlightTarget>
          ))}
        </div>
      )}
    </div>
  );
}

const COMPOSITION_COLOR: Record<string, string> = {
  starters: "var(--color-information)",
  roster: "var(--color-information)",
  bench: "var(--color-premium)",
  ir: "var(--color-danger)",
  taxi: "var(--color-warning)",
};

export function RosterCompositionBar({ segments }: { segments: CompositionSegment[] }) {
  return (
    <div className="glass-surface flex flex-col gap-3 p-4">
      <div
        className="flex w-full overflow-hidden"
        style={{ height: 12, borderRadius: 999 }}
        role="img"
        aria-label={segments.map((s) => `${s.label} ${s.percent}%`).join(", ")}
      >
        {segments.map((segment) => (
          <span
            key={segment.key}
            style={{ width: `${segment.percent}%`, background: COMPOSITION_COLOR[segment.key] ?? "var(--color-text-muted)" }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              style={{
                width: 8,
                height: 8,
                borderRadius: 999,
                background: COMPOSITION_COLOR[segment.key] ?? "var(--color-text-muted)",
              }}
            />
            {segment.label}
            <span className="font-bold" style={{ color: "var(--color-text-primary)" }}>
              {segment.percent}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

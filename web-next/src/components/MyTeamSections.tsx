"use client";

import { useId, useState, type ReactNode } from "react";

import { HighlightTarget } from "@/components/HighlightTarget";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerRow } from "@/components/PlayerRow";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueStat } from "@/components/ValueStat";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import type { KeeperPlayerInfo, LineupPlayer } from "@/lib/api";
import type { CompositionSegment, TeamAnalysisRow } from "@/lib/myTeamAnalysis";
import { CompactModule } from "@/components/ui/CompactModule";
import { listSummaryParts } from "@/lib/moduleTemplates";
import { formatScore, lineupIneligibleTag, sumScore } from "@/lib/myTeamPresentation";
import { EmptyState } from "@/components/EmptyState";
import { playerSurname } from "@/lib/playerNameDisplay";

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

const TONE_LEVEL: Record<TeamAnalysisRow["tone"], number> = { success: 4, information: 3, warning: 2, danger: 1 };

/** Four-segment strength meter for a position room, filled and tinted from the row's tone. */
function RoomMeter({ tone, position }: { tone: TeamAnalysisRow["tone"]; position: string }) {
  const level = TONE_LEVEL[tone];
  return (
    <span className="flex w-full max-w-[9rem] gap-1" role="img" aria-label={`${position} room strength ${level} of 4`}>
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="flex-1 h-1.5"
          style={{
            borderRadius: "var(--radius-pill)",
            background: i <= level ? TONE_VAR[tone] : "var(--color-surface-muted)",
          }}
        />
      ))}
    </span>
  );
}

/** One row per position room: status badge + strength meter; tap for the full
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
              <span className="flex flex-1 flex-col items-start gap-1.5 min-w-0">
                <ToneBadge label={row.status} color={TONE_VAR[row.tone]} />
                <RoomMeter tone={row.tone} position={row.position} />
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
  if (player.slot === "IDP_FLEX") return "IDP";
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
  // A team defense has no player record behind it: no Quick View, no OVR.
  const isTeamDefense = (player.position || "").toUpperCase() === "DEF";
  const ineligibleTag = lineupIneligibleTag(player);
  const surplus = surplusText(keeper);
  return (
    <PlayerRow
      bordered
      identity={isTeamDefense ? undefined : identity}
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
          {isTeamDefense ? null : (
            <button
              type="button"
              aria-label={`Open ${player.name || "player"}`}
              onClick={() => openPlayer(identity)}
              className="inline-flex items-center justify-center -my-3 min-w-[var(--touch-target-min)] min-h-[var(--touch-target-min)]"
              style={{ background: "none", border: "none", cursor: "pointer" }}
            >
              <Chevron />
            </button>
          )}
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

/**
 * The roster as sections, not tabs (IA rule R1: the page's only tab row is the family strip). Each group is a
 * CompactModule that reads while collapsed ("9 players · Value 6,120 · Gibbs, Chase") and opens inline into the rows.
 * Starters opens by default; the group holding `highlightPlayerId` (a deep link) opens too.
 */
export function RosterSections({
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
  const highlighted = tabs.find((tab) => highlightPlayerId && tab.players.some((p) => p.player_id === highlightPlayerId))?.value;
  return (
    <div className="flex flex-col gap-2">
      {tabs.map((tab, index) => {
        const names = tab.players.slice(0, 3).map((p) => playerSurname(p.name || "")).filter(Boolean);
        const total = sumScore(tab.players);
        return (
          <CompactModule
            key={tab.value}
            id={`team.roster.${tab.value}`}
            title={tab.label}
            testId={`roster-section-${tab.value}`}
            tone={tab.muted ? "muted" : "accent"}
            defaultOpen={highlighted ? highlighted === tab.value : index === 0}
            parts={listSummaryParts({
              count: tab.players.length,
              noun: "player",
              none: emptyText,
              highlights: [total > 0 ? `Value ${formatScore(total)}` : null, names.length > 0 ? names.join(", ") : null],
              maxHighlights: 2,
            })}
          >
            {index === 0 ? topNote : null}
            {tab.players.length === 0 ? (
              <EmptyState title={emptyText} />
            ) : (
              <div className="flex flex-col px-1">
                {tab.players.map((player) => (
                  <HighlightTarget key={player.player_id} active={player.player_id === highlightPlayerId}>
                    <RosterRow player={player} keeper={keepers?.[player.player_id]} muted={tab.muted ?? false} showSlot={tab.showSlot ?? false} />
                  </HighlightTarget>
                ))}
              </div>
            )}
          </CompactModule>
        );
      })}
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

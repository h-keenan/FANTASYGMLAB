"use client";

import { useState, type ReactNode } from "react";

import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { TickNumber } from "@/components/TickNumber";
import { ToneBadge } from "@/components/ToneBadge";
import {
  PLAYER_CARD_AVATAR_SIZE,
  formatCardPoints,
  headlinePoints,
  playerCardAriaLabel,
  playerGameLine,
  playerStatusChips,
  trendVsProjection,
  type ChipTone,
  type PlayerCardModel,
  type PlayerCardVariant,
} from "@/lib/playerCard";
import { positionColorVar } from "@/lib/playerPresentation";

/**
 * THE player card (docs/player-card.md). One props-driven component with three
 * variants so a player looks the same everywhere:
 *
 *  - `compact`: list row. Photo, name, position/team, status chips, 1-2 stats.
 *  - `matchup`: head-to-head row. Live/final points big, projected final with a
 *    green/red trend, game line, game-progress bar, optional expandable detail.
 *  - `card`: larger tile for rosters and grids, with the value (OVR) ring.
 *
 * Tapping the card opens the shared Player Quick View (PlayerIdentityTrigger).
 * Never a bare "photo + name + number": every variant carries position, team
 * and a status chip. What it says comes from lib/playerCard.ts (shared with
 * the app).
 */

export interface PlayerCardStat {
  label: string;
  value: string;
}

const CHIP_COLOR: Record<ChipTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

export function PlayerStatusChips({ model }: { model: PlayerCardModel }) {
  const chips = playerStatusChips(model);
  if (chips.length === 0) return null;
  return (
    <>
      {chips.map((chip) => (
        <ToneBadge
          key={chip.kind}
          size="xs"
          testId={`player-chip-${chip.kind}`}
          label={chip.kind === "live" ? "● LIVE" : chip.label}
          srLabel={chip.label}
          color={CHIP_COLOR[chip.tone]}
        />
      ))}
    </>
  );
}

function TrendArrow({ dir }: { dir: "up" | "down" | "flat" }) {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      {dir === "flat" ? (
        <path d="M1 5h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      ) : (
        <path
          d={dir === "up" ? "M5 9V1M1.5 4.5 5 1l3.5 3.5" : "M5 1v8M1.5 5.5 5 9l3.5-3.5"}
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      )}
    </svg>
  );
}

function accentStyle(position: string | null): React.CSSProperties | undefined {
  const colorVar = positionColorVar(position);
  return colorVar ? ({ "--pc-accent": `var(${colorVar})` } as React.CSSProperties) : undefined;
}

export interface PlayerCardProps {
  variant: PlayerCardVariant;
  model: PlayerCardModel;
  /** Opens Player Quick View on tap. Omit for a non-interactive card. */
  identity?: PlayerQuickViewIdentity | null;
  /** Planner mode: tapping swaps instead of opening Quick View. */
  onEdit?: () => void;
  editLabel?: string;
  /** Matchup: mirror the layout on wide screens so numbers face the center. */
  mirror?: boolean;
  emphasis?: "win" | "lose" | "even";
  /** compact / card: 1-2 trailing stats. */
  stats?: PlayerCardStat[];
  /** Matchup: bump to re-run the "points just changed" pulse. */
  pulseKey?: number;
  /** Matchup: extra content shown when expanded (a default is built from the model). */
  detail?: ReactNode;
  /** Matchup: "YOU" / "OPP" tag shown on phones, where the two cards are stacked. */
  sideTag?: "you" | "opp";
  /** Free slot after the stats (e.g. a trailing action). */
  trailing?: ReactNode;
}

export function PlayerCard(props: PlayerCardProps) {
  if (props.variant === "matchup") return <MatchupCard {...props} />;
  if (props.variant === "card") return <TileCard {...props} />;
  return <CompactCard {...props} />;
}

function Wrap({
  identity,
  onEdit,
  editLabel,
  model,
  className,
  children,
}: Pick<PlayerCardProps, "identity" | "onEdit" | "editLabel" | "model"> & { className: string; children: ReactNode }) {
  if (onEdit) {
    return (
      <button type="button" onClick={onEdit} aria-label={editLabel ?? `Swap ${model.name}`} className={`${className} text-left`}>
        {children}
      </button>
    );
  }
  if (identity) {
    return (
      <PlayerIdentityTrigger identity={identity} className={className}>
        {children}
      </PlayerIdentityTrigger>
    );
  }
  return <div className={className}>{children}</div>;
}

function NameBlock({ model, size }: { model: PlayerCardModel; size: PlayerCardVariant }) {
  const line = [model.team].filter(Boolean).join(" · ");
  return (
    <span className="flex flex-col min-w-0 flex-1 gap-1">
      <PlayerName
        name={model.name}
       
        className={`${size === "compact" ? "text-sm" : "text-[13px]"} font-bold leading-tight w-full`}
        style={{ color: "var(--color-text-primary)" }}
      />
      <span className="flex items-center gap-1 flex-wrap min-w-0">
        <PositionBadge position={model.position} />
        {size === "compact" && line ? (
          <span className="text-[11px] truncate" style={{ color: "var(--color-text-muted)" }}>
            {line}
          </span>
        ) : null}
        <PlayerStatusChips model={model} />
      </span>
    </span>
  );
}

function CompactCard({ model, identity, onEdit, editLabel, stats = [], trailing }: PlayerCardProps) {
  return (
    <div className="player-card player-card--compact" data-testid="player-card-compact" style={accentStyle(model.position)}>
      <div className="flex items-center gap-2.5 min-w-0">
        <Wrap identity={identity} onEdit={onEdit} editLabel={editLabel} model={model} className="flex items-center gap-2.5 flex-1 min-w-0">
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.compact}
            fallbackLabel={model.team}
          />
          <NameBlock model={model} size="compact" />
        </Wrap>
        {stats.slice(0, 2).map((stat) => (
          <span key={stat.label} className="flex flex-col items-end shrink-0">
            <span className="text-sm font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
              {stat.value}
            </span>
            <span className="text-[10px] uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
              {stat.label}
            </span>
          </span>
        ))}
        {trailing}
      </div>
    </div>
  );
}

function TileCard({ model, identity, onEdit, editLabel, stats = [], trailing }: PlayerCardProps) {
  return (
    <div className="player-card player-card--card gap-2.5" data-testid="player-card-tile" style={accentStyle(model.position)}>
      <Wrap identity={identity} onEdit={onEdit} editLabel={editLabel} model={model} className="flex flex-col gap-2 min-w-0">
        <span className="flex items-start justify-between gap-2">
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.card}
            fallbackLabel={model.team}
          />
          <OvrGauge rating={model.overallRating} size="md" />
        </span>
        <NameBlock model={model} size="card" />
        <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>
          {playerGameLine(model) || model.team || ""}
        </span>
      </Wrap>
      {stats.length > 0 ? (
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(stats.length, 3)}, minmax(0, 1fr))` }}>
          {stats.slice(0, 3).map((stat) => (
            <span key={stat.label} className="flex flex-col">
              <span className="text-sm font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
                {stat.value}
              </span>
              <span className="text-[10px] uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                {stat.label}
              </span>
            </span>
          ))}
        </div>
      ) : null}
      {trailing}
    </div>
  );
}

function trendColor(dir: "up" | "down" | "flat"): string {
  return dir === "up" ? "var(--color-success)" : dir === "down" ? "var(--color-danger)" : "var(--color-text-muted)";
}

export function PlayerCardDetail({ model }: { model: PlayerCardModel }) {
  const rows: [string, string][] = [];
  if (model.projection != null) rows.push(["Pre-game projection", formatCardPoints(model.projection)]);
  if (model.points != null) rows.push(["Points so far", formatCardPoints(model.points)]);
  if (model.projectedFinal != null) rows.push(["Projected final", formatCardPoints(model.projectedFinal)]);
  if (model.overallRating != null) rows.push(["Overall rating", String(Math.round(model.overallRating))]);
  if (model.slot) rows.push(["Lineup slot", model.slot]);
  if (model.injuryLabel) rows.push(["Injury status", model.injuryLabel]);
  if (rows.length === 0) return <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>No more detail yet.</p>;
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs m-0">
      {rows.map(([term, value]) => (
        <div key={term} className="contents">
          <dt style={{ color: "var(--color-text-muted)" }}>{term}</dt>
          <dd className="m-0 text-right font-bold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function MatchupCard({ model, identity, onEdit, editLabel, mirror = false, emphasis = "even", pulseKey = 0, detail, sideTag }: PlayerCardProps) {
  const [open, setOpen] = useState(false);
  const head = headlinePoints(model);
  const trend = trendVsProjection(model);
  const live = model.gameStatus === "in_progress";
  const unavailable = model.bye || model.out;
  const flip = mirror ? " sm:flex-row-reverse" : "";
  const align = mirror ? " sm:text-right sm:items-end" : "";
  return (
    <div
      className="player-card player-card--matchup"
      data-testid="player-card-matchup"
      data-emphasis={emphasis}
      data-unavailable={unavailable ? "true" : undefined}
      data-live={live ? "true" : undefined}
      style={accentStyle(model.position)}
      aria-label={playerCardAriaLabel(model)}
    >
      {pulseKey > 0 ? <span key={pulseKey} className="player-card-pulse" data-testid="player-card-pulse" aria-hidden="true" /> : null}
      <div className={`flex items-center gap-2.5 min-w-0${flip}`}>
        <Wrap
          identity={identity}
          onEdit={onEdit}
          editLabel={editLabel}
          model={model}
          className={`flex items-center gap-2.5 flex-1 min-w-0${flip}`}
        >
          <PlayerAvatar
            playerId={model.playerId}
            tier={model.tier}
            size={PLAYER_CARD_AVATAR_SIZE.matchup}
            fallbackLabel={model.team}
          />
          <span className={`flex flex-col min-w-0 flex-1 gap-1${align}`}>
            <PlayerName
              name={model.name}
             
              className="text-[13px] font-bold leading-tight w-full"
              style={{ color: "var(--color-text-primary)" }}
            />
            <span className={`flex items-center gap-1 flex-wrap min-w-0${mirror ? " sm:justify-end" : ""}`}>
              {sideTag ? (
                <span className="sm:hidden" data-testid="side-tag">
                  <ToneBadge size="xs" label={sideTag === "you" ? "YOU" : "OPP"} color={sideTag === "you" ? "var(--color-accent)" : "var(--color-text-muted)"} />
                </span>
              ) : null}
              <PositionBadge position={model.position} />
              <PlayerStatusChips model={model} />
            </span>
            <span className="text-[11px] leading-tight truncate w-full" style={{ color: "var(--color-text-muted)" }} data-testid="player-card-game-line">
              {[model.team, playerGameLine(model)].filter(Boolean).join(" · ")}
            </span>
          </span>
        </Wrap>
        <span className={`flex flex-col items-end shrink-0 text-right gap-0.5${mirror ? " sm:items-start sm:text-left" : ""}`}>
          {head.value != null ? (
            <TickNumber
              value={head.value}
              testId="player-card-points"
              className="player-card-points text-xl font-extrabold leading-none"
              style={{ color: head.kind === "pts" ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
            />
          ) : (
            <span className="player-card-points text-xl font-extrabold leading-none" style={{ color: "var(--color-text-muted)" }}>
              {unavailable ? "0.0" : "—"}
            </span>
          )}
          <span className="text-[10px] uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            {head.kind === "pts" ? (model.gameStatus === "final" ? "Final pts" : "Pts") : head.kind === "proj" ? "Proj" : model.bye ? "Bye" : ""}
          </span>
          {model.projectedFinal != null ? (
            <span
              className="inline-flex items-center gap-1 text-[11px] font-bold tabular-nums"
              style={{ color: trend ? trendColor(trend.dir) : "var(--color-text-secondary)" }}
              data-testid="proj-final"
              title={trend ? `${trend.delta > 0 ? "+" : ""}${trend.delta.toFixed(1)} vs pre-game projection` : undefined}
            >
              {trend ? <TrendArrow dir={trend.dir} /> : null}
              Proj final {model.projectedFinal.toFixed(1)}
            </span>
          ) : model.gameStatus === "final" && trend ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold tabular-nums" style={{ color: trendColor(trend.dir) }}>
              <TrendArrow dir={trend.dir} />
              {trend.delta > 0 ? "+" : ""}
              {trend.delta.toFixed(1)} vs proj
            </span>
          ) : null}
        </span>
      </div>
      {model.gameStatus ? (
        <span
          className="player-card-progress"
          data-final={model.gameStatus === "final" ? "true" : undefined}
          role="progressbar"
          aria-label="Game progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(model.progress * 100)}
        >
          <span style={{ width: `${Math.round(model.progress * 100)}%` }} />
        </span>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? `Hide ${model.name} details` : `Show ${model.name} details`}
        className="self-start text-[11px] font-bold inline-flex items-center gap-1"
        style={{ color: "var(--color-text-muted)" }}
      >
        <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true" style={{ transform: open ? "rotate(180deg)" : undefined }}>
          <path d="M1.5 3.5 5 7l3.5-3.5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {open ? "Less" : "Details"}
      </button>
      {open ? <div data-testid="player-card-detail">{detail ?? <PlayerCardDetail model={model} />}</div> : null}
    </div>
  );
}

/** Placeholder card for an open lineup slot. */
export function EmptySlotCard({ onEdit }: { onEdit?: () => void }) {
  const body = (
    <span className="text-xs italic" style={{ color: onEdit ? "var(--color-accent)" : "var(--color-text-muted)" }}>
      {onEdit ? "Empty, tap to fill" : "Empty slot"}
    </span>
  );
  return (
    <div className="player-card player-card--matchup justify-center" data-unavailable="true" data-testid="player-card-empty" style={{ minHeight: 64 }}>
      {onEdit ? (
        <button type="button" onClick={onEdit} className="text-left">
          {body}
        </button>
      ) : (
        body
      )}
    </div>
  );
}

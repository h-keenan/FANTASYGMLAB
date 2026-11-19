"use client";

import type { ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PositionBadge } from "@/components/PositionBadge";
import { Tabs } from "@/components/Tabs";
import { ToneBadge } from "@/components/ToneBadge";
import {
  teamSheetLevelLabel,
  teamSheetLevelTone,
  teamSheetPositionLine,
  teamSheetStreakTone,
  type TeamSheetChip,
  type TeamSheetPosition,
  type TeamSheetTile,
} from "@/lib/teamSheet";

/**
 * THE team sheet (header, Overview / Roster / Trades / History tabs, Overview tiles, streak line, strengths
 * and needs cards). The Fantasy Sim sheet and the Desk (real Sleeper) sheet both render through it and only
 * supply data and slots, so the two can never look different. Mobile twin: components/TeamSheet.tsx.
 */

const TONE_COLOR: Record<string, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-secondary)",
  accent: "var(--color-accent)",
  premium: "var(--color-premium)",
};

export interface TeamSheetTab {
  key: string;
  label: string;
  render: () => ReactNode;
}

export function TeamSheetFrame({
  id,
  logo,
  name,
  nameTestId,
  nameId,
  tag,
  chips,
  managedBy,
  managerIsAi = false,
  tabs,
}: {
  id: string;
  logo: ReactNode;
  name: string;
  nameTestId?: string;
  nameId?: string;
  /** The trade-style tag slot (a badge, or the Free upsell). */
  tag?: ReactNode;
  chips: TeamSheetChip[];
  managedBy?: string | null;
  /** The manager is an AI: draws the small bot mark (lib/simManagerLabel.ts). */
  managerIsAi?: boolean;
  tabs: TeamSheetTab[];
}) {
  return (
    <div className="flex flex-col gap-4 pr-1">
      <header className="flex items-center gap-3 pr-10">
        {logo}
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-lg font-extrabold break-words" id={nameId} data-testid={nameTestId}>{name}</p>
          <div className="flex flex-wrap items-center gap-2">
            {tag}
            {chips.map((c) => (
              <ToneBadge key={c.label} label={c.label} color={TONE_COLOR[c.tone]} size="xs" />
            ))}
          </div>
          {managedBy ? (
            <p className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="team-sheet-manager">
              Managed by{" "}
              {managerIsAi ? (
                <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" role="img" aria-label="AI manager">
                  <rect x="4" y="8" width="16" height="12" rx="3" />
                  <path d="M12 4v4M9 13h.01M15 13h.01" />
                </svg>
              ) : null}
              {managedBy}
            </p>
          ) : null}
        </div>
      </header>
      <Tabs id={id} ariaLabel="Team sections" tabs={tabs} />
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-surface flex flex-col items-center px-1 py-1.5">
      <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span className="text-sm font-extrabold tabular-nums">{value}</span>
    </div>
  );
}

/** The Overview tab body: description, tiles, streak line, strengths and needs, injuries. Titles and injury rows are slots so each surface keeps its own heading and player-row look. */
export function TeamSheetOverview({
  blurb,
  tiles,
  streak,
  nextGame,
  positions,
  strengthsTitle,
  injuries,
}: {
  blurb?: ReactNode;
  tiles: TeamSheetTile[];
  streak?: string | null;
  nextGame?: string;
  positions: TeamSheetPosition[];
  strengthsTitle: ReactNode;
  injuries?: ReactNode;
}) {
  return (
    <>
      {blurb ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{blurb}</p> : null}
      <div className="grid grid-cols-4 gap-2" aria-label="Season so far">
        {tiles.map((t) => (
          <Tile key={t.label} label={t.label} value={t.value} />
        ))}
      </div>
      {streak || nextGame ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {streak ? (
            <>
              Streak <strong style={{ color: TONE_COLOR[teamSheetStreakTone(streak)] }}>{streak}</strong>
              {nextGame ? ` · ${nextGame}` : ""}
            </>
          ) : (
            nextGame
          )}
        </p>
      ) : null}
      <section className="flex flex-col gap-2" aria-label="Strengths and needs">
        {strengthsTitle}
        <ul className="grid grid-cols-3 gap-2">
          {positions.map((p) => {
            const color = TONE_COLOR[teamSheetLevelTone(p.level)];
            return (
              <li key={p.pos}>
                <AccentCard accent={color} compact as="div">
                  <div className="flex flex-col items-start gap-1">
                    <PositionBadge position={p.pos} />
                    <span className="text-xs font-extrabold" style={{ color }}>{teamSheetLevelLabel(p.level)}</span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{teamSheetPositionLine(p)}</p>
                </AccentCard>
              </li>
            );
          })}
        </ul>
      </section>
      {injuries}
    </>
  );
}

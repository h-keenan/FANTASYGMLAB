"use client";

import { Fragment, useCallback, useState, type ReactNode } from "react";

import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { LetterGrade } from "@/components/ui/LetterGrade";
import { PlayerBadges } from "@/components/ui/PlayerBadge";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { nextOpenId, playerRowModel, type FactTone, type PlayerFactsInput, type PlayerFact } from "@/lib/playerAnatomy";
import type { BadgeInput } from "@/lib/playerBadges";
import type { SimGradeInput } from "@/lib/simGrade";

const TONE: Record<FactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

/** One open row at a time across a list: `const acc = usePlayerAccordion(); <PlayerAccordionRow open={acc.isOpen(id)} onToggle={() => acc.toggle(id)} />`. */
export function usePlayerAccordion() {
  const [openId, setOpenId] = useState<string | null>(null);
  const toggle = useCallback((id: string) => setOpenId((cur) => nextOpenId(cur, id)), []);
  return { openId, toggle, isOpen: (id: string) => openId === id };
}

function Fact({ fact }: { fact: PlayerFact }) {
  return (
    <div className="flex min-w-0 flex-col" data-fact={fact.key}>
      <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{fact.label}</span>
      <span className="text-sm font-extrabold tabular-nums" style={{ color: fact.tone ? TONE[fact.tone] : "var(--color-text-primary)" }}>{fact.value}</span>
    </div>
  );
}

export type PlayerAccordionRowProps = PlayerFactsInput & {
  open: boolean;
  onToggle: () => void;
  badges?: BadgeInput[];
  /** Replaces the position pill text (a lineup slot such as "FLEX"). */
  positionLabel?: string | null;
  /** The ONE primary action of the expanded tile (the only gold control), e.g. "Trade ideas" / "Draft". */
  primaryAction?: ReactNode;
  /** Opens the full player sheet (PQV). */
  onOpenProfile?: () => void;
  /** Extra expanded content (reasons, notes). */
  children?: ReactNode;
  testId?: string;
  /** Screen-reader name for the row button (defaults to the player name). */
  ariaLabel?: string;
  /** Sim: the letter grade, drawn as a small tile at the end of the stats line (never a "GRADE" word, never in the trailing slot). */
  gradeTile?: SimGradeInput | null;
  /** Replaces the TEAM · Age · Bye line (the caller's parts, with the bye-soon tone and PROJ); one line, truncated. */
  metaParts?: { key: string; text: string; tone?: FactTone }[];
  /** Drop the position pill when a slot label column already says it. */
  hidePosition?: boolean;
  /**
   * THE one trailing control of the row (the sim's Move button): a sibling of the row button, never nested in it. The row
   * itself stays one tap target that expands in place, so a row has one always-visible control and no more.
   */
  trailingAction?: ReactNode;
};

/**
 * THE player row (docs/ui-patterns.md, "Player anatomy"). Compact: a two-line inline accordion row (avatar, name +
 * position badge, TEAM · age · bye, one trailing key number or letter grade; no chevron because the whole row is the
 * tap target). Tapped it swells in place into a glass tile with projections / value / trend and the actions. Serves
 * FantasyDesk (`mode="desk"`) and Fantasy Sim (`mode="sim"`: grade, ADP, projection; never OVR or trade value).
 * Mobile twin: components/PlayerAccordionRow.tsx; logic: lib/playerAnatomy.ts.
 */
export function PlayerAccordionRow({ open, onToggle, badges = [], positionLabel, primaryAction, onOpenProfile, children, testId = "player-accordion-row", ariaLabel, gradeTile, metaParts, hidePosition = false, trailingAction, ...input }: PlayerAccordionRowProps) {
  const { player } = input;
  const model = playerRowModel(input);
  const metaLine: { key: string; text: string; tone?: FactTone }[] = metaParts ?? model.meta.map((text, i) => ({ key: `m${i}`, text }));
  return (
    <div
      className="min-w-0"
      data-testid={testId}
      data-open={open ? "true" : "false"}
      style={
        open
          ? {
              background: "var(--glass-bg, var(--color-surface))",
              border: "1px solid var(--color-accent)",
              borderRadius: "var(--radius-panel)",
              boxShadow: "var(--glass-shadow, none)",
              padding: "0.25rem 0.5rem 0.625rem",
              margin: "0.25rem 0",
            }
          : { borderBottom: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)", padding: "0.125rem 0.5rem" }
      }
    >
      <div className="flex min-w-0 items-center gap-1.5">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={ariaLabel}
          className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
          style={{ minHeight: "var(--touch-target-min)" }}
        >
          <PlayerAvatarSlot player={player} tier="row" />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="flex min-w-0 items-center gap-1.5">
              <PlayerName name={player.name} className="min-w-0 text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
              {hidePosition ? null : <PositionBadge position={player.position} label={positionLabel ?? undefined} />}
              <PlayerBadges badges={badges} />
            </span>
            {metaLine.length > 0 || gradeTile ? (
              <span className="flex min-w-0 items-center gap-1.5 text-xs leading-4" style={{ color: "var(--color-text-muted)" }} data-testid="row-meta">
                <span className="min-w-0 truncate">
                  {metaLine.map((part, i) => (
                    <Fragment key={part.key}>
                      {i > 0 ? " · " : ""}
                      <span style={{ color: part.tone ? TONE[part.tone] : undefined, fontWeight: part.tone === "warning" || part.key === "proj" ? 700 : undefined }}>{part.text}</span>
                    </Fragment>
                  ))}
                </span>
                {gradeTile ? <LetterGrade grade={gradeTile} size="xs" testId="row-grade" /> : null}
              </span>
            ) : null}
          </span>
          {model.trailing && input.mode !== "sim" ? (
            <span className="flex shrink-0 flex-col items-end" data-testid="row-trailing">
              <span className="text-base font-extrabold tabular-nums leading-5" style={{ color: model.trailing.tone ? TONE[model.trailing.tone] : "var(--color-text-primary)" }}>{model.trailing.value}</span>
              <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{model.trailing.label}</span>
            </span>
          ) : null}
        </button>
        {trailingAction ? <span className="flex shrink-0 items-center" data-testid="row-action">{trailingAction}</span> : null}
      </div>
      {open ? (
        <div className="row-expand"><div className="row-expand-inner flex flex-col gap-2.5 pt-1" data-testid="row-expanded">
          {model.facts.length > 0 ? (
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(4, model.facts.length)}, minmax(0, 1fr))` }}>
              {model.facts.map((fact) => <Fact key={fact.key} fact={fact} />)}
            </div>
          ) : null}
          {children}
          {primaryAction || onOpenProfile ? (
            <div className="flex flex-wrap items-center gap-2">
              {primaryAction}
              {onOpenProfile ? (
                <button
                  type="button"
                  onClick={onOpenProfile}
                  className="inline-flex items-center justify-center px-3 text-sm font-bold"
                  style={{ minHeight: "var(--touch-target-min)", border: "1px solid var(--color-border-strong)", borderRadius: "var(--radius-control)", color: "var(--color-text-primary)", background: "transparent" }}
                >
                  Open profile
                </button>
              ) : null}
            </div>
          ) : null}
        </div></div>
      ) : null}
    </div>
  );
}

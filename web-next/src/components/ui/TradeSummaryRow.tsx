"use client";

import { useState, type ReactNode } from "react";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { Collapse } from "@/components/ui/Presence";
import type { TradeOutcomeChip } from "@/lib/tradeOutcomeChips";

export interface TradeSummaryPlayer {
  key: string;
  playerId: string | null;
  name: string;
  position?: string | null;
}

const CHIP_COLOR = { success: "var(--color-success)", muted: "var(--color-text-secondary)" } as const;

/**
 * The compact one-card trade row (Trade History): a PlayerAvatar for each side, "A for B" on one line, small chips for the
 * result and the date muted. One calm card: no verdict stripe, no red (a loss is a muted "Down 12" chip, never red).
 * For the full give / get card with fairness meter see `TradeCompactCard`. Mobile twin: components/TradeSummaryRow.tsx.
 */
export function TradeSummaryRow({
  partner,
  send,
  receive,
  swapText,
  chips,
  date,
  testId = "trade-summary-row",
  children,
}: {
  partner: string;
  send: TradeSummaryPlayer[];
  receive: TradeSummaryPlayer[];
  /** "A for B", already shortened. */
  swapText: string;
  chips: TradeOutcomeChip[];
  date?: string;
  testId?: string;
  /** Details shown on tap (the read, the exchange). */
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className="glass-surface flex min-w-0 flex-col gap-1.5 p-3" style={{ borderRadius: "var(--radius-panel)" }} data-testid={testId}>
      <div className="flex min-w-0 items-center gap-2">
        <span className="inline-flex shrink-0 items-center -space-x-2" aria-hidden="true">
          {[...send.slice(0, 2), ...receive.slice(0, 2)].map((p) => (
            <PlayerAvatar key={p.key} playerId={p.playerId} name={p.name} position={p.position} size={32} />
          ))}
        </span>
        <div className="min-w-0 flex-1">
          <p className="m-0 truncate text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>{swapText || partner}</p>
          <p className="m-0 truncate text-xs" style={{ color: "var(--color-text-muted)" }}>
            {partner}
            {date ? ` · ${date}` : ""}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((chip) => (
          <ToneBadge key={chip.key} label={chip.label} color={CHIP_COLOR[chip.tone]} />
        ))}
      </div>
      {children ? (
        <>
          <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="self-start text-xs font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}>
            {open ? "Hide details" : "Show details"}
          </button>
          <Collapse open={open}><div className="flex flex-col gap-3">{children}</div></Collapse>
        </>
      ) : null}
    </article>
  );
}

"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/components/Button";
import { FairnessMeterRow } from "@/components/ui/FairnessMeterRow";
import { TradeAssetCard, type TradeCardAsset } from "@/components/ui/TradeCompactCard";
import { fairnessMeter, type FairnessMeter, type PlayerMode } from "@/lib/playerAnatomy";
import { tradeScaleCount, tradeScaleMissing, tradeScalePhase } from "@/lib/tradeScale";

export type TradeScaleSide = "give" | "get";

function Column({
  side,
  label,
  assets,
  mode,
  max,
  editing,
  addHint,
  onAdd,
  onRemove,
}: {
  side: TradeScaleSide;
  label: string;
  assets: TradeCardAsset[];
  mode: PlayerMode;
  max?: number | null;
  editing: boolean;
  addHint?: string;
  onAdd: (side: TradeScaleSide) => void;
  onRemove?: (side: TradeScaleSide, key: string) => void;
}) {
  const full = Boolean(max && assets.length >= max);
  return (
    <div className="glass-surface flex min-w-0 flex-col gap-1 p-2" data-testid={`scale-${side}`} style={{ borderRadius: "var(--radius-panel)" }}>
      <span className="flex items-center gap-1.5 text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        <span aria-hidden="true" className="inline-block" style={{ width: 6, height: 6, borderRadius: "50%", background: side === "give" ? "var(--color-danger)" : "var(--color-success)" }} />
        {label}
        <span className="tabular-nums">{tradeScaleCount(assets.length, max)}</span>
      </span>
      {assets.map((a) => (
        <div key={a.key} className="enter-rise flex min-w-0 items-center gap-1" data-testid="scale-asset">
          <div className="min-w-0 flex-1">
            <TradeAssetCard asset={a} mode={mode} />
          </div>
          {editing && onRemove ? (
            <button type="button" aria-label={`Remove ${a.player?.name ?? a.pickLabel ?? "asset"}`} onClick={() => onRemove(side, a.key)} className="inline-flex shrink-0 items-center justify-center text-base font-bold" style={{ width: 32, minHeight: "var(--touch-target-min)", color: "var(--color-text-muted)" }}>
              ×
            </button>
          ) : null}
        </div>
      ))}
      <div className="scale-collapse" data-open={editing && !full ? "true" : "false"} aria-hidden={editing && !full ? undefined : true}>
        <div className="scale-collapse-inner">
          <button
            type="button"
            tabIndex={editing && !full ? 0 : -1}
            onClick={() => onAdd(side)}
            aria-label={assets.length ? `${label}: add more` : `${label}: add players or picks${addHint ? ` (${addHint})` : ""}`}
            className="flex w-full flex-col items-center justify-center text-sm font-extrabold"
            style={{ minHeight: assets.length ? "var(--touch-target-min)" : 64, border: "1px dashed var(--color-accent)", borderRadius: "var(--radius-control)", color: "var(--color-accent)", background: "transparent" }}
            data-testid={`scale-add-${side}`}
          >
            <span aria-hidden="true">+</span>
            {assets.length === 0 && addHint ? <span className="px-1 text-center text-[0.6875rem] font-bold" style={{ color: "var(--color-text-muted)" }}>{addHint}</span> : null}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * The trade builder's "two-column scale" (coridian_ pick, ui-pass-3 topic 3 V1): Give and Get sit side by side as compact
 * player cards, the fairness meter lives under them and updates live, "+" opens the picker sheet, a card opens the player
 * peek, and once both sides are filled the verdict replaces the add buttons with Send / Tweak (Tweak brings the "+" tiles
 * and remove buttons back; "Review" returns). `mode="sim"` passes its own plain-word `meter` and never a value.
 * Shared by the Trade Analyzer, the offer builder and the Fantasy Sim builder. Mobile twin: components/TradeScale.tsx;
 * model: lib/tradeScale.ts.
 */
export function TradeScale({
  give,
  get,
  mode = "desk",
  giveLabel = "You send",
  getLabel = "You get",
  max,
  meter,
  netValue,
  addHint,
  onAdd,
  onRemove,
  verdict,
  onSend,
  canSend = true,
  sending = false,
  sendLabel = "Send offer",
  footer,
  buildingAction,
  testId = "trade-scale",
}: {
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  giveLabel?: string;
  getLabel?: string;
  /** Per-side asset cap (shown as "2 of 6"; the "+" tile hides at the cap). */
  max?: number | null;
  /** The meter to draw. Desk omits it and gets `fairnessMeter` from the asset values (`netValue` wins when the server has one). */
  meter?: FairnessMeter;
  netValue?: number | null;
  addHint?: { give?: string; get?: string };
  onAdd: (side: TradeScaleSide) => void;
  onRemove?: (side: TradeScaleSide, key: string) => void;
  /** Shown instead of the add buttons when the offer is ready (the verdict card). */
  verdict?: ReactNode;
  /** Send. Omit to hide it (the verdict has its own action, such as taking a counter). */
  onSend?: () => void;
  canSend?: boolean;
  sending?: boolean;
  sendLabel?: string;
  /** Small line under the meter (roster after the trade, notes). */
  footer?: ReactNode;
  /** Shown while the offer is still being built (one side empty), e.g. the Analyzer's one-sided "Analyze" button. */
  buildingAction?: ReactNode;
  testId?: string;
}) {
  const [tweaking, setTweaking] = useState(false);
  const phase = tradeScalePhase({ giveCount: give.length, getCount: get.length, tweaking });
  const editing = phase !== "review";
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const missing = tradeScaleMissing(give.length, get.length);
  const live = meter ?? fairnessMeter(sum(give), sum(get), mode, netValue);
  const shown: FairnessMeter = missing ? { position: 0.5, edge: 0, label: missing, description: missing, tone: "muted" } : live;
  return (
    <section className="flex min-w-0 flex-col gap-2" data-testid={testId} data-phase={phase} aria-label="Trade">
      <div className="grid grid-cols-2 gap-2">
        <Column side="give" label={giveLabel} assets={give} mode={mode} max={max} editing={editing} addHint={addHint?.give} onAdd={onAdd} onRemove={onRemove} />
        <Column side="get" label={getLabel} assets={get} mode={mode} max={max} editing={editing} addHint={addHint?.get} onAdd={onAdd} onRemove={onRemove} />
      </div>
      <div className="glass-surface flex flex-col gap-1 p-2" style={{ borderRadius: "var(--radius-panel)" }}>
        <FairnessMeterRow meter={shown} />
        {footer}
      </div>
      {(phase === "building" || phase === "empty") && buildingAction ? <div className="flex flex-col gap-2" data-testid="scale-building-action">{buildingAction}</div> : null}
      {phase === "review" || phase === "tweak" ? (
        <div className="enter-rise flex flex-col gap-2" key={phase} data-testid="scale-actions">
          {phase === "review" ? verdict : null}
          <div className="flex flex-wrap items-center gap-2">
            {phase === "review" ? (
              <>
                {onSend ? <Button loading={sending} disabled={!canSend} onClick={onSend}>{sendLabel}</Button> : null}
                <Button variant="secondary" onClick={() => setTweaking(true)}>Tweak</Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setTweaking(false)}>Review</Button>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

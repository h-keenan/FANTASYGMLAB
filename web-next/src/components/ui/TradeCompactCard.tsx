"use client";

import { useId, useState, type ReactNode } from "react";

import { OvrGauge } from "@/components/OvrGauge";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { fairnessMeter, type FactTone, type PlayerMode, type PlayerRef } from "@/lib/playerAnatomy";

export interface TradeCardAsset {
  key: string;
  /** A player renders as a compact player card (avatar included); a pick passes `pickLabel`. */
  player?: PlayerRef;
  pickLabel?: string;
  detail?: string | null;
  /** Desk only: the asset's value, shown as the card's trailing number. */
  value?: number | null;
  /** Desk only: overall rating gauge beside the value. */
  ovr?: number | null;
  /** Tap the card to open the player sheet. */
  onOpen?: () => void;
}

const TONE: Record<FactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

function TapWrap({ onOpen, label, children }: { onOpen?: () => void; label: string; children: ReactNode }) {
  if (!onOpen) return <>{children}</>;
  return (
    <button type="button" onClick={onOpen} aria-label={`Open ${label}`} className="block w-full min-w-0 text-left" style={{ background: "none", border: 0, padding: 0 }}>
      {children}
    </button>
  );
}

function Side({ label, assets, mode }: { label: string; assets: TradeCardAsset[]; mode: PlayerMode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1" data-testid={`trade-side-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{label}</span>
      {assets.map((a) =>
        a.player ? (
          <TapWrap key={a.key} onOpen={a.onOpen} label={a.player.name}>
          <CompactPlayerCard player={a.player} detail={a.detail} trailing={
              mode === "desk" && (a.value != null || a.ovr != null) ? (
                <span className="inline-flex items-center gap-1.5">
                  {a.ovr != null ? <OvrGauge rating={a.ovr} size="sm" /> : null}
                  {a.value != null ? Math.round(a.value).toLocaleString() : null}
                </span>
              ) : undefined
            } />
          </TapWrap>
        ) : (
          <div key={a.key} className="flex items-center text-sm font-bold" style={{ minHeight: 40 }}>{a.pickLabel}</div>
        ),
      )}
    </div>
  );
}

/**
 * Trade card (idea / offer / inbox): the involved players as compact player cards on a give and a get side, a
 * fairness meter row (recommended V3), and details that expand in place. `mode="sim"` shows plain words and grades,
 * never the hidden value. Shared by Trade Hub, Trade Finder, GM Plan and the Sim trade inbox. Mobile twin:
 * components/TradeCompactCard.tsx.
 */
export function TradeCompactCard({
  title,
  give,
  get,
  mode = "desk",
  verdictLabel,
  netValue,
  children,
  defaultOpen = false,
  testId = "trade-compact-card",
  giveLabel = "You send",
  getLabel = "You get",
  meta = [],
}: {
  title: ReactNode;
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  /** Overrides the meter's computed label (e.g. the server's value-edge band). */
  verdictLabel?: string | null;
  /** The server's net value for the trade (positive = you win); wins over the asset sums, which can miss pick values. */
  netValue?: number | null;
  /** Details shown when expanded (reasoning, odds, share). */
  children?: ReactNode;
  defaultOpen?: boolean;
  testId?: string;
  giveLabel?: string;
  getLabel?: string;
  /** Short facts under the title (e.g. "High confidence"). */
  meta?: string[];
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const meter = fairnessMeter(sum(give), sum(get), mode, netValue);
  const hasBody = children != null && children !== false;
  return (
    <section className="glass-surface flex min-w-0 flex-col gap-2 p-3" data-testid={testId} style={{ borderRadius: "var(--radius-panel)" }}>
      <div className="min-w-0 text-sm font-extrabold">{title}</div>
      {meta.length > 0 ? <div className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="trade-card-meta">{meta.join(" · ")}</div> : null}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Side label={giveLabel} assets={give} mode={mode} />
        <Side label={getLabel} assets={get} mode={mode} />
      </div>
      <div className="flex items-center gap-2" data-testid="fairness-meter">
        <div className="relative h-2 flex-1 rounded-full" style={{ background: "rgba(255,255,255,0.12)" }} role="img" aria-label={verdictLabel && mode === "desk" ? `${meter.description}. Market read: ${verdictLabel}` : meter.description}>
          <span
            className="absolute top-0 h-full rounded-full"
            style={{ left: `${Math.min(50, meter.position * 100)}%`, width: `${Math.abs(meter.position - 0.5) * 100}%`, background: TONE[meter.tone], opacity: 0.55 }}
            aria-hidden="true"
            data-testid="fairness-fill"
          />
          <span className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2" style={{ left: "50%", background: "var(--color-text-muted)" }} aria-hidden="true" />
          <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: `${meter.position * 100}%`, background: TONE[meter.tone], boxShadow: "0 0 0 2px var(--color-surface-muted)" }} aria-hidden="true" data-testid="fairness-marker" />
        </div>
        <span className="shrink-0 text-xs font-extrabold" style={{ color: TONE[meter.tone] }} data-testid="fairness-label">{meter.label}</span>
      </div>
      {hasBody ? (
        <>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((v) => !v)}
            className="self-start text-xs font-bold"
            style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
          >
            {open ? "Hide details" : "Show details"}
          </button>
          <div id={bodyId} hidden={!open} className="flex flex-col gap-3">{open ? children : null}</div>
        </>
      ) : null}
    </section>
  );
}

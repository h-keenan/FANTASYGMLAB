"use client";

import { easeCss, MOTION_MS } from "@/lib/motion";
import type { FactTone, FairnessMeter } from "@/lib/playerAnatomy";

const TONE: Record<FactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

/**
 * THE fairness meter row: a centre-anchored track, a fill from the centre to the marker, and the label. The marker and fill
 * glide between values (`MOTION_MS.base`) so a live edit reads as the scale tipping; reduced motion snaps. Used by
 * `TradeCompactCard` (read-only) and `TradeScale` (the builder, updating live). Mobile twin: components/FairnessMeterRow.tsx.
 */
export function FairnessMeterRow({ meter, ariaLabel }: { meter: FairnessMeter; ariaLabel?: string }) {
  const glide = `${MOTION_MS.base}ms ${easeCss("out")}`;
  return (
    <div className="flex items-center gap-2" data-testid="fairness-meter">
      <div className="relative h-2 flex-1 rounded-full" style={{ background: "rgba(255,255,255,0.12)" }} role="img" aria-label={ariaLabel ?? meter.description}>
        <span
          className="fairness-glide absolute top-0 h-full rounded-full"
          style={{ left: `${Math.min(50, meter.position * 100)}%`, width: `${Math.abs(meter.position - 0.5) * 100}%`, background: TONE[meter.tone], opacity: 0.55, transition: `left ${glide}, width ${glide}, background ${glide}` }}
          aria-hidden="true"
          data-testid="fairness-fill"
        />
        <span className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2" style={{ left: "50%", background: "var(--color-text-muted)" }} aria-hidden="true" />
        <span
          className="fairness-glide absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: `${meter.position * 100}%`, background: TONE[meter.tone], boxShadow: "0 0 0 2px var(--color-surface-muted)", transition: `left ${glide}, background ${glide}` }}
          aria-hidden="true"
          data-testid="fairness-marker"
        />
      </div>
      <span className="shrink-0 text-xs font-extrabold" style={{ color: TONE[meter.tone] }} data-testid="fairness-label" aria-live="polite">{meter.label}</span>
    </div>
  );
}

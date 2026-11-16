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
 * glide between values (transform only) (`MOTION_MS.base`) so a live edit reads as the scale tipping; reduced motion snaps. Used by
 * `TradeCompactCard` (read-only) and `TradeScale` (the builder, updating live). Mobile twin: components/FairnessMeterRow.tsx.
 */
export function FairnessMeterRow({ meter, ariaLabel }: { meter: FairnessMeter; ariaLabel?: string }) {
  const glide = `${MOTION_MS.base}ms ${easeCss("out")}`;
  return (
    <div className="flex items-center gap-2" data-testid="fairness-meter">
      <div className="relative h-2 flex-1 rounded-full" style={{ background: "rgba(255,255,255,0.12)" }} role="img" aria-label={ariaLabel ?? meter.description}>
        {/* Fill from the centre to the marker: two half-width bars scaled out from the centre (transform only). */}
        <span
          className="fairness-glide absolute top-0 h-full rounded-full"
          style={{ left: "50%", width: "50%", transformOrigin: "left center", transform: `scaleX(${Math.max(0, meter.position - 0.5) * 2})`, background: TONE[meter.tone], opacity: 0.55, transition: `transform ${glide}, background ${glide}` }}
          aria-hidden="true"
          data-testid="fairness-fill"
        />
        <span
          className="fairness-glide absolute top-0 h-full rounded-full"
          style={{ left: 0, width: "50%", transformOrigin: "right center", transform: `scaleX(${Math.max(0, 0.5 - meter.position) * 2})`, background: TONE[meter.tone], opacity: 0.55, transition: `transform ${glide}, background ${glide}` }}
          aria-hidden="true"
          data-testid="fairness-fill-left"
        />
        <span className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2" style={{ left: "50%", background: "var(--color-text-muted)" }} aria-hidden="true" />
        {/* The marker rides a full-width carrier moved by percent of its own width (transform only). */}
        <span
          className="fairness-glide absolute left-0 top-0 h-full w-full"
          style={{ transform: `translateX(${meter.position * 100}%)`, transition: `transform ${glide}` }}
          aria-hidden="true"
          data-testid="fairness-marker"
        >
          <span className="absolute left-0 top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ background: TONE[meter.tone], boxShadow: "0 0 0 2px var(--color-surface-muted)", transition: `background ${glide}` }} />
        </span>
      </div>
      <span className="shrink-0 text-xs font-extrabold" style={{ color: TONE[meter.tone] }} data-testid="fairness-label" aria-live="polite">{meter.label}</span>
    </div>
  );
}

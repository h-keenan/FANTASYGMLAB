"use client";

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { Money } from "@/components/Money";
import { fitMetaParts, type MetaPart } from "@/lib/playerMetaFit";
import type { FactTone } from "@/lib/playerAnatomy";

const TONE: Record<FactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
};

/**
 * THE sub-line under a player name (docs/ui-patterns.md, "Never ellipsize"): parts leave by the ladder in
 * lib/playerMetaFit.ts (Age, then team, then a bye that is not soon) when the width is short, the projection / status never
 * leave, and whatever is left wraps instead of being cut. `trailing` (the letter grade tile) rides at the end and is
 * reserved before the parts are fitted. Mobile twin: components/PlayerMetaLine.tsx.
 */
export function PlayerMetaLine({ parts, trailing, trailingPx = 0, fontPx = 12, testId = "row-meta" }: { parts: readonly MetaPart[]; trailing?: ReactNode; trailingPx?: number; fontPx?: number; testId?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [width, setWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setWidth(el.getBoundingClientRect().width);
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const shown = fitMetaParts(parts, width, fontPx);
  return (
    <span className="flex min-w-0 items-start gap-1.5 text-xs leading-4" style={{ color: "var(--color-text-muted)" }} data-testid={testId}>
      <span ref={ref} className="flex min-w-0 flex-1 flex-wrap" data-testid="row-meta-parts">
        {shown.map((part, i) => (
          <span key={part.key} className="whitespace-nowrap" data-meta={part.key} style={{ color: part.tone ? TONE[part.tone as FactTone] : undefined, fontWeight: part.tone === "warning" || part.key === "proj" ? 700 : undefined }}>
            <Money>{part.text}</Money>
            {i < shown.length - 1 ? <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>{" · "}</span> : null}
          </span>
        ))}
      </span>
      {trailing ? <span className="shrink-0" style={{ minWidth: trailingPx || undefined }}>{trailing}</span> : null}
    </span>
  );
}

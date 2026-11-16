"use client";

import { SuccessCheck } from "@/components/Motion";

/**
 * What a trade card collapses into once it is answered (motion audit candidate 3): a single row with the
 * `SuccessCheck` for an accepted trade or a muted cross for a declined one. The card swaps to it through
 * `PresenceSwap` (see `TradeCompactCard`'s `resolved` prop and the Sim inbox). Mobile twin: components/TradeResolvedRow.tsx.
 */
export function TradeResolvedRow({ kind, label, testId = "trade-resolved" }: { kind: "accepted" | "declined"; label: string; testId?: string }) {
  return (
    <div className="flex items-center gap-2 py-1 text-sm font-bold" style={{ minHeight: "var(--touch-target-min)" }} data-testid={testId} data-resolved={kind} role="status">
      {kind === "accepted" ? (
        <SuccessCheck size={24} label="Trade done" />
      ) : (
        <span aria-hidden="true" className="inline-flex items-center justify-center rounded-full text-xs" style={{ width: 24, height: 24, color: "var(--color-text-muted)", border: "1.5px solid currentColor" }}>
          {"✕"}
        </span>
      )}
      <span style={{ color: kind === "accepted" ? "var(--color-success)" : "var(--color-text-secondary)" }}>{label}</span>
    </div>
  );
}

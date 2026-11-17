"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { SLOW_LOAD_AFTER_MS, SLOW_LOAD_RETRY_AFTER_MS, SLOW_LOAD_RETRY_LABEL, SLOW_LOAD_TEXT } from "@/lib/badDayCopy";

/**
 * Rendered inside a page-level skeleton: after SLOW_LOAD_AFTER_MS it says the load is slow, after SLOW_LOAD_RETRY_AFTER_MS it offers
 * a retry. A skeleton never sits there silently (docs/audits/2026-11-bad-day-and-words.md). The request itself times out at 30s and
 * the page then shows the shared ErrorState. Mobile twin: components/SlowLoadNote.tsx.
 */
export function SlowLoadNote({ onRetry }: { onRetry?: () => void }) {
  const [phase, setPhase] = useState<0 | 1 | 2>(0);
  useEffect(() => {
    const slow = setTimeout(() => setPhase(1), SLOW_LOAD_AFTER_MS);
    const retry = setTimeout(() => setPhase(2), SLOW_LOAD_RETRY_AFTER_MS);
    return () => {
      clearTimeout(slow);
      clearTimeout(retry);
    };
  }, []);
  if (phase === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="slow-load-note">
      <p role="status" className="min-w-0 flex-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
        {SLOW_LOAD_TEXT}
      </p>
      {phase === 2 ? (
        <Button size="sm" variant="secondary" onClick={onRetry ?? (() => window.location.reload())}>
          {SLOW_LOAD_RETRY_LABEL}
        </Button>
      ) : null}
    </div>
  );
}

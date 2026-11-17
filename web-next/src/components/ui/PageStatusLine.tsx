"use client";

import type { ReactNode } from "react";

/**
 * THE one compact page sub-line (UI audit batch B, docs/audits/2026-11-ui-audit-e2e.md P0-2): context on the left ("Week 10", a Live
 * badge), freshness + a refresh icon on the right, one row about 32px tall, then the standard small gap (`--page-top-gap`) to the first
 * module. It replaces the separate title/week row and the separate "Updated 3m ago . Refresh" row, and pages must not repeat what it
 * says (the week) inside the first card. The 44px refresh target is kept by negative block margins, so the row stays compact.
 * Mobile twin: mobile/src/components/PageStatusLine.tsx.
 */
export function PageStatusLine({
  context,
  freshness,
  onRefresh,
  refreshing = false,
  refreshLabel = "Refresh",
  testId = "page-status-line",
}: {
  context?: ReactNode;
  /** "Updated 3m ago"; omit when there is nothing to show. */
  freshness?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
  refreshLabel?: string;
  testId?: string;
}) {
  if (!context && !freshness && !onRefresh) return null;
  return (
    <div className="page-status-line" data-testid={testId}>
      <div className="flex min-w-0 items-center gap-2 text-sm font-bold" style={{ color: "var(--color-text-secondary)" }}>
        {context}
      </div>
      <div className="flex shrink-0 items-center text-xs" style={{ color: "var(--color-text-muted)" }}>
        {freshness ? <span aria-live="polite">{freshness}</span> : null}
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label={refreshing ? "Refreshing" : refreshLabel}
            className="page-status-refresh"
            data-testid={`${testId}-refresh`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              className={refreshing ? "page-status-spin" : undefined}
            >
              <path d="M21 12a9 9 0 1 1-2.64-6.36" />
              <path d="M21 3v6h-6" />
            </svg>
          </button>
        ) : null}
      </div>
    </div>
  );
}

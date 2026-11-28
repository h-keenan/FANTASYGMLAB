"use client";

import { useId, useState, type ReactNode } from "react";

import { Collapse } from "@/components/ui/Presence";

/**
 * One short line with a "Why" toggle: the line is always visible, the longer reason opens under it on tap (compact,
 * tap-to-expand; docs/ui-patterns.md). Replaces a stacked explanatory paragraph. Mobile twin: components/WhyLine.tsx.
 */
export function WhyLine({ line, children, label, testId }: { line: ReactNode; children: ReactNode; /** Plain-text name for the toggle's accessible label. */ label: string; testId?: string }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  return (
    <div className="flex flex-col" data-testid={testId}>
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-xs font-semibold" style={{ color: "var(--color-text-secondary)" }}>
          {line}
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={`${label}. ${open ? "Hide" : "Show"} why`}
          className="shrink-0 px-2 text-xs font-bold"
          style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }}
        >
          Why {open ? "⌃" : "⌄"}
        </button>
      </div>
      <Collapse open={open} id={bodyId}>
        <p className="pb-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {children}
        </p>
      </Collapse>
    </div>
  );
}

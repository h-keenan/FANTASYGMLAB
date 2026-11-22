"use client";

import { useId, useState, type ReactNode } from "react";

import { Collapse } from "@/components/ui/Presence";

/**
 * THE one-line expandable row (docs/ui-patterns.md, "ExpandRow"): a leading mark (usually a player avatar), ONE short
 * line, an optional trailing action, and a chevron. Tapping the line opens `children` (the full reason / detail) under
 * it; the trailing action works without opening. Rows sit in an `ExpandRowGroup` (one grouped surface with dividers, never
 * a card per row). Used by Today's "Do this now" and its More list. Mobile twin: components/ExpandRow.tsx.
 */
export function ExpandRow({
  leading,
  title,
  caption,
  action,
  children,
  testId,
  label,
  defaultOpen = false,
}: {
  leading?: ReactNode;
  /** The one short line (at most about six words). */
  title: ReactNode;
  /** Optional muted second part on the same line (a figure, a count). */
  caption?: ReactNode;
  /** The row's one button / link; sits outside the toggle so it is usable collapsed. */
  action?: ReactNode;
  /** The detail behind the tap. Omit for a row that is only a line + action. */
  children?: ReactNode;
  testId?: string;
  /** Plain-text name for the toggle's accessible label. */
  label: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const hasBody = children != null && children !== false;
  const line = (
    <>
      {leading}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm font-bold leading-snug">{title}</span>
        {caption ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {caption}
          </span>
        ) : null}
      </span>
    </>
  );
  return (
    <li className="flex flex-col" data-testid={testId}>
      <div className="flex items-center gap-2" style={{ minHeight: 48 }}>
        {hasBody ? (
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls={bodyId} aria-label={`${label}. ${open ? "Hide" : "Show"} details`} className="flex min-w-0 flex-1 items-center gap-2 text-left" style={{ minHeight: 48, color: "inherit" }} data-testid={testId ? `${testId}-toggle` : undefined}>
            {line}
            <span aria-hidden="true" className="shrink-0 text-sm" style={{ color: "var(--color-text-muted)", transform: open ? "rotate(180deg)" : undefined }}>
              ⌄
            </span>
          </button>
        ) : (
          <span className="flex min-w-0 flex-1 items-center gap-2">{line}</span>
        )}
        {action ? <span className="shrink-0">{action}</span> : null}
      </div>
      {hasBody ? (
        <Collapse open={open} id={bodyId}>
          <div className="flex flex-col gap-2 pb-2 pt-1">{children}</div>
        </Collapse>
      ) : null}
    </li>
  );
}

/** The grouped surface for a stack of ExpandRows: one glass card, hairline dividers between rows. */
export function ExpandRowGroup({ accent, children, testId }: { accent: string; children: ReactNode; testId?: string }) {
  return (
    <ul className="glass-surface m-0 flex list-none flex-col px-3 py-0 [&>li+li]:border-t [&>li+li]:border-[var(--color-border)]" style={{ borderLeft: `var(--border-width-semantic) solid ${accent}`, borderRadius: "var(--radius-card, 12px)" }} data-testid={testId}>
      {children}
    </ul>
  );
}

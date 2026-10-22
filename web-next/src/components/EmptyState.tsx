import type { ReactNode } from "react";

import { Button } from "@/components/Button";

/**
 * The one empty state: a glass card with a title, a one-line reason and, when
 * there is a sensible next step, a button for it (College Scouting style).
 * Use it instead of a bare muted `<p>` when a whole list or panel is empty.
 */
export function EmptyState({
  title,
  subtitle,
  actionLabel,
  onAction,
  children,
}: {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="glass-surface flex flex-col gap-1 items-start px-4 py-6" data-testid="empty-state">
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {title}
      </p>
      {subtitle ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {subtitle}
        </p>
      ) : null}
      {children}
      {actionLabel && onAction ? (
        <Button size="sm" onClick={onAction} className="mt-2">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

import type { ReactNode } from "react";

import { Button } from "@/components/Button";

/** Default glyph for an empty list/panel (inbox tray) or an error (alert triangle); currentColor outline. */
export function EmptyStateGlyph({ name = "inbox", size = 22 }: { name?: "inbox" | "alert"; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {name === "alert" ? (
        <>
          <path d="M12 3.5 2.8 19.5h18.4L12 3.5Z" />
          <path d="M12 10v4.5" />
          <path d="M12 17.4v.1" />
        </>
      ) : (
        <>
          <path d="M3.5 13.5 6.2 5.8A1.5 1.5 0 0 1 7.6 4.8h8.8a1.5 1.5 0 0 1 1.4 1l2.7 7.7" />
          <path d="M3.5 13.5v4.2a1.5 1.5 0 0 0 1.5 1.5h14a1.5 1.5 0 0 0 1.5-1.5v-4.2h-5.2a3.3 3.3 0 0 1-6.6 0H3.5Z" />
        </>
      )}
    </svg>
  );
}

/**
 * The one icon-in-a-ring badge used by empty and error states: a tinted
 * circle (15% fill of `accent`) around a glyph. `accent` is a semantic token.
 */
export function StateIconRing({ accent, children }: { accent: string; children: ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center"
      style={{
        width: 44,
        height: 44,
        borderRadius: 9999,
        color: accent,
        background: `color-mix(in srgb, ${accent} 15%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${accent} 30%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

/**
 * The one empty state: a glass card with an accent left rail, an icon ring,
 * a title, a one-line reason and, when there is a sensible next step, a
 * button for it. Use it instead of a bare muted `<p>` when a whole list or
 * panel is empty. `icon` swaps the default glyph, `accent` the rail/ring
 * color (a semantic token), `centered` stacks the content for a full-width
 * dead screen.
 */
export function EmptyState({
  title,
  subtitle,
  actionLabel,
  onAction,
  children,
  icon,
  accent = "var(--color-accent)",
  centered = false,
}: {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  children?: ReactNode;
  icon?: ReactNode;
  accent?: string;
  centered?: boolean;
}) {
  return (
    <div
      className={`glass-surface flex gap-3 px-4 py-5 ${centered ? "flex-col items-center text-center" : "items-start"}`}
      style={{ borderLeft: `var(--border-width-semantic) solid ${accent}` }}
      data-testid="empty-state"
    >
      <StateIconRing accent={accent}>{icon ?? <EmptyStateGlyph />}</StateIconRing>
      <div className={`flex min-w-0 flex-1 flex-col gap-1 ${centered ? "items-center" : "items-start"}`}>
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
    </div>
  );
}

import type { ReactNode } from "react";

/**
 * Uppercase page-section title (`--type-section-title`), with an optional
 * accent kicker above it and a muted note below it. Extracted from five
 * identical local copies (MyTeamContent, WaiversContent, MatchupContent,
 * LeagueRankingsContent, PlayerCompareContent's `SectionHeader`) that each
 * restated the same font/letter-spacing pair. Markup is unchanged from
 * those copies: a bare `<h2>` when there is no kicker/note, otherwise the
 * kicker/title/note column LeagueRankingsContent used.
 *
 * One scale (coridian_ 2026-11-14, UI pass 5 D2): `--type-app-section-title`, 18px / 800, the app's heading size. The old big
 * 21.6px / 900 default is gone; public SEO pages keep `--type-section-title` for their own h2s.
 *
 * See docs/ui-module-inventory.md: sentence-case section titles (Dashboard,
 * Draft Center, Live Draft, GM Plan) are a separate, still-undecided
 * variant and deliberately not folded in here.
 */
export function SectionHeading({
  children,
  kicker,
  note,
  id,
  className = "flex flex-col gap-1",
  action,
  help,
}: {
  children: ReactNode;
  /** Small accent label above the title (e.g. "Head-to-Head"). */
  kicker?: string;
  /** Muted caption line below the title. */
  note?: string;
  id?: string;
  /** Wrapper classes, only used when a kicker or note is present. */
  className?: string;
  /** Right-aligned slot on the title row (e.g. a "View All" link). */
  action?: ReactNode;
  /** Inline help (<InfoMark label=...>) placed directly after the title it explains, never at the far edge. */
  help?: ReactNode;
}) {
  const font = "var(--type-app-section-title)";
  const title = (
    <h2 id={id} className="uppercase" style={{ font, letterSpacing: "0.02em" }}>
      {children}
    </h2>
  );
  const titled = help ? (
    <div className="flex items-center min-w-0">
      {title}
      {help}
    </div>
  ) : (
    title
  );
  if (action) {
    return (
      <div className="flex items-center justify-between gap-3">
        {titled}
        {/* .section-heading-action gives a bare link/button here the 44px
            touch target (globals.css) without each caller adding padding. */}
        <div className="section-heading-action shrink-0">{action}</div>
      </div>
    );
  }
  if (!kicker && !note) return titled;
  return (
    <div className={className}>
      {kicker ? (
        <span
          className="uppercase font-extrabold"
          style={{ font: "var(--type-supporting-metadata)", color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          {kicker}
        </span>
      ) : null}
      {titled}
      {note ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}

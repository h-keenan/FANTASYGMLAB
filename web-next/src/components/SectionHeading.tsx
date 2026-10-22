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
}) {
  const title = (
    <h2 id={id} className="uppercase" style={{ font: "var(--type-section-title)", letterSpacing: "0.02em" }}>
      {children}
    </h2>
  );
  if (action) {
    return (
      <div className="flex items-baseline justify-between gap-3">
        {title}
        {action}
      </div>
    );
  }
  if (!kicker && !note) return title;
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
      {title}
      {note ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}

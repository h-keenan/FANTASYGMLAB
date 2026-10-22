/**
 * Small uppercase status badge tinted from one semantic color (15% fill of
 * the same color as the text). Two shapes exist on the site today and both
 * are kept as-is (see docs/ui-module-inventory.md B9 — which one should win
 * is an open owner decision):
 *
 * - `outline` — square, 1px border in the tone color. Was
 *   LeagueRankingsContent's `RankBadge`, WaiversContent's
 *   `RecommendationPill`, and the Guess-the-Player leaderboard's "You" tag.
 * - `pill` — rounded capsule, badge letter-spacing, no border. Was
 *   TradeHistoryContent's `Badge`, Portfolio's signal badge, and Alerts'
 *   roster-relationship badge.
 *
 * `color` is a CSS color expression, normally a semantic token such as
 * `var(--color-success)` — never a raw hex.
 */
export function ToneBadge({
  label,
  color,
  variant = "outline",
}: {
  label: string;
  color: string;
  variant?: "outline" | "pill";
}) {
  if (variant === "pill") {
    return (
      <span
        className="px-1.5 py-0.5 text-xs font-extrabold uppercase whitespace-nowrap"
        style={{
          borderRadius: "var(--radius-pill)",
          background: `color-mix(in srgb, ${color} 15%, transparent)`,
          color,
          letterSpacing: "var(--letter-spacing-badge)",
        }}
      >
        {label}
      </span>
    );
  }
  return (
    <span
      className="px-1.5 py-0.5 text-xs font-extrabold uppercase shrink-0"
      style={{ background: `color-mix(in srgb, ${color} 15%, transparent)`, color, border: `1px solid ${color}` }}
    >
      {label}
    </span>
  );
}

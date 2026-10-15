/**
 * Portfolio's quick-glance league cards show up to PORTFOLIO_MAX_SIGNALS
 * (modules/dashboard_engine.py) per-league "Next Move" signals — the exact
 * same BriefingItem shape and `category` taxonomy Today's Game Plan's
 * GamePlanCard already renders (top_priority / watch / waiver_opportunity /
 * league_movement), just several per league instead of one hero item.
 *
 * This is a genuinely different taxonomy from Alerts' `event_type`
 * (injury/status, transaction, role/depth chart, off-field/drama) —
 * alertsPresentation.ts's labels/tones don't apply here, so this is its own
 * small, focused helper rather than a forced reuse of that file. Mirrors
 * modules/portfolio_page.py's `_CATEGORY_BADGE_VARIANT`/
 * `_CATEGORY_GLYPH_CONCEPT` and modules/daily_gm_briefing.py's
 * `CATEGORY_LABELS` onto this app's existing `--color-danger` / `--color-
 * warning` / `--color-opportunity` / `--color-information` semantic tokens
 * (the same tokens GamePlanCard, SnapshotTile, and AlertsContent already use
 * for tone), instead of inventing a new badge-color system for this page.
 */

export const CATEGORY_LABELS: Record<string, string> = {
  top_priority: "Top Priority",
  watch: "Watch",
  waiver_opportunity: "Waiver Opportunity",
  league_movement: "League Movement",
};

export function categoryLabel(category: string | null | undefined): string {
  if (!category) return "Next Move";
  if (CATEGORY_LABELS[category]) return CATEGORY_LABELS[category];
  return category
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

/** Same danger/caution/opportunity/information mapping as
 * modules/portfolio_page.py's `_CATEGORY_BADGE_VARIANT`, onto this app's
 * `--color-*` tokens (caution -> warning, the token name this app uses). */
export function categoryColorVar(category: string | null | undefined): string {
  if (category === "top_priority") return "var(--color-danger)";
  if (category === "watch") return "var(--color-warning)";
  if (category === "waiver_opportunity") return "var(--color-opportunity)";
  if (category === "league_movement") return "var(--color-information)";
  return "var(--color-text-secondary)";
}

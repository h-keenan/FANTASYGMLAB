/**
 * Free-vs-Pro comparison rows for the paywall surfaces (/premium and the
 * onboarding paywall). The live rows come from GET /v1/me `premium_comparison`,
 * built server-side from the enforced limits in modules/premium_benefits.py
 * (gm_targets.MAX_TARGETS_*, trade_hub_presentation.FREE_VISIBLE_IDEAS,
 * FREE_NEXT_MOVE_ITEMS, saved_leagues caps), so numbers cannot drift from the
 * gates. FALLBACK_PREMIUM_COMPARISON only renders when that fetch fails; keep
 * it equal to the server output (tests/test_premium_conversion_intent_flow.py
 * guards the server side). Mirrors mobile/src/lib/premiumComparison.ts.
 */
export interface PremiumComparisonRow {
  key: string;
  label: string;
  free: string;
  pro: string;
}

export const FALLBACK_PREMIUM_COMPARISON: PremiumComparisonRow[] = [
  { key: "next_moves", label: "Next Moves", free: "Top 4", pro: "Your full briefing" },
  { key: "trade_hub", label: "Trade Hub ideas", free: "First 2", pro: "Every idea" },
  { key: "gm_targets", label: "GM Targets", free: "3 players", pro: "50 players" },
  { key: "waivers", label: "Waiver board", free: "Priority Adds", pro: "Full board, stashes, FAAB" },
  { key: "league_pulse", label: "League Pulse leaders", free: "Activity only", pro: "Contender, rebuilder, picks" },
  { key: "leagues", label: "Saved leagues", free: "1 league", pro: "Unlimited" },
];

/** Validates the wire value; anything malformed or empty yields the fallback. */
export function normalizePremiumComparison(value: unknown): PremiumComparisonRow[] {
  if (!Array.isArray(value)) return FALLBACK_PREMIUM_COMPARISON;
  const rows = value.filter(
    (r): r is PremiumComparisonRow =>
      !!r &&
      typeof r === "object" &&
      typeof (r as PremiumComparisonRow).key === "string" &&
      typeof (r as PremiumComparisonRow).label === "string" &&
      typeof (r as PremiumComparisonRow).free === "string" &&
      typeof (r as PremiumComparisonRow).pro === "string",
  );
  return rows.length > 0 ? rows : FALLBACK_PREMIUM_COMPARISON;
}

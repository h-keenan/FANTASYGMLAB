/**
 * What a Pro page contains, shown before the Upgrade button (UX utilization
 * audit 2026-11-03, 4.2: "paywalls that show one paragraph and no preview").
 * Plain, concrete statements of what the feature does, taken from the same
 * descriptions the server's wall copy and the Pro page already use: no
 * fabricated numbers and no sample data. A real fact about the person's own
 * league is added by the page when it already has one (see `example` on
 * PremiumUpsellCard). Mirrors web-next/src/lib/paidPreviews.ts: keep the keys
 * and copy identical.
 */
export interface PaidPreview {
  /** What the page shows once unlocked. */
  bullets: string[];
  /** What Free still includes on this surface, when that is true and useful. */
  freeIncludes?: string;
}

/** Keys match PremiumUpsellCard's gate key (the kicker, snake-cased). */
export function paidPreview(key: string, leagueName?: string): PaidPreview | null {
  const league = leagueName?.trim() || "your league";
  switch (key) {
    case "draft_center":
      return {
        bullets: [
          `Your draft posture, from your roster and where you stand in ${league}`,
          `Pick decision signals across every team in ${league}`,
          "The best trade partners for your picks",
        ],
      };
    case "live_draft":
      return {
        bullets: [
          "Best Available and Best Fit picks while your Sleeper draft runs",
          "A live roster-strength board",
          "Alerts when a position run starts",
        ],
      };
    case "commissioner":
      return {
        bullets: [
          "Per-team lineup efficiency",
          "Tanking signals, with the evidence behind them",
          "Repeated lopsided trades",
          "Inactive managers",
        ],
      };
    case "college_scouting":
      return {
        bullets: [
          "The shared college prospect board",
          "Community grades for each prospect",
          "Your own scouting reports and watchlist",
        ],
      };
    case "portfolio":
      return {
        bullets: [
          "Your record and rank in every saved league",
          "Each league's biggest need or opportunity",
          "All of your leagues side by side",
        ],
        freeIncludes: "Free keeps one saved league.",
      };
    case "exposure":
      return {
        bullets: ["Which players you own across every league", "How concentrated your portfolio is"],
      };
    case "gm_plan":
      return {
        bullets: [
          "Where you stand, in one read",
          "Your best trade paths",
          "Roster construction, framed by your declared Team Situation",
        ],
        freeIncludes: "Free keeps your Team Situation, protected players and the watch list.",
      };
    case "playoff_odds":
      return {
        bullets: [
          `A rest-of-season simulation of ${league}'s real schedule`,
          "Every team's playoff chance and projected seed",
        ],
        freeIncludes: "Free keeps the standings and every power ranking on this page.",
      };
    case "what_if":
      return {
        bullets: ["Add or drop players and see the change in your playoff odds before you make the move"],
      };
    case "trade_finder":
      return {
        bullets: [
          `Build a custom package and search every roster in ${league}`,
          "Realistic packages, with near misses labelled",
        ],
        freeIncludes: "Free keeps the Trade Analyzer and the first 2 Trade Hub ideas.",
      };
    default:
      return null;
  }
}

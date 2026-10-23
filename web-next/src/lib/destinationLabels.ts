/**
 * CTA labels for Game Plan / Watchlist destinations. Every destination now
 * routes to a real Next.js page (see gamePlanPresentation.ts's
 * GAME_PLAN_INTERNAL_ROUTES); any unknown destination falls back to the
 * league Dashboard.
 */
export const DESTINATION_LABELS: Record<string, string> = {
  trade_hub: "Review in Trade Hub",
  waivers: "Open Waivers",
  my_team: "Open My Team",
  rankings: "Open League Rankings",
  gm_plan: "Open GM Plan",
  dashboard: "Open workflow",
  // GM Targets (Revision 11) has no in-page add flow (see GmTargetsContent's
  // own docstring) — its empty state sends a user to add a first target.
  // Players now has a real Next.js page (Revision 16) — see
  // GamePlanCard.tsx's INTERNAL_ROUTES, which routes this destination there
  // instead of here.
  players: "Open Players",
  // Trade Analyzer (Revision 15) has a real Next.js page now — see
  // GamePlanCard.tsx's INTERNAL_ROUTES, which routes this destination there
  // instead of here. Trade Finder (Revision 17) is the same again — it
  // also now routes internally via GamePlanCard.tsx's INTERNAL_ROUTES and
  // TradesTabBar.tsx, rather than deep-linking to Streamlit.
  trade_analyzer: "Open Trade Analyzer",
  trade_finder: "Open Trade Finder",
  team_situation: "Review Team Situation",
};

export function destinationCtaLabel(destination: string): string {
  return DESTINATION_LABELS[destination] ?? "Open workflow";
}

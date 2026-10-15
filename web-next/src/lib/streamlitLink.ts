import { env } from "./env";

/**
 * Every other page still lives in Streamlit, unchanged, for this Revision
 * (see PR description). "Open X" / quick-action cards on the Next.js
 * Dashboard deep-link out to Streamlit's own single-page router, which
 * reads the page to show from a `?page=` query param
 * (app.py's `st.query_params["page"]`, see `_pending_platform_route` /
 * `platform_nav_page`). Streamlit has no concept of league context in the
 * URL — the league itself resolves from the signed-in account's saved/
 * default league or the guest's in-session selection, so there is no
 * league_id to thread through this link.
 */
export function streamlitPageUrl(destination: string): string {
  const page = destination || "dashboard";
  return `${env.streamlitBaseUrl}/?page=${encodeURIComponent(page)}`;
}

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
};

export function destinationCtaLabel(destination: string): string {
  return DESTINATION_LABELS[destination] ?? "Open workflow";
}

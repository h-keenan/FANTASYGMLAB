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
  dashboard: "Open workflow",
};

export function destinationCtaLabel(destination: string): string {
  return DESTINATION_LABELS[destination] ?? "Open workflow";
}

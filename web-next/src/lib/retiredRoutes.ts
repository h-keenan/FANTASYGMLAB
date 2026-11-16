import { leagueRecapsHref } from "@/lib/newsLinks";
import { parseRecapsTab, parseRoundupWeek } from "@/lib/pageTabs";

/**
 * Where each page retired by the 2026-11-16 nav consolidation now lives. The old route stays (so every bookmark, push
 * deep link and shared URL keeps working) and redirects here, carrying the league id and name along.
 *
 *  - /alerts/[id]        -> Today's Alerts section        /dashboard/[id]#alerts
 *  - /live-draft/[id]    -> the Draft page's live room    /draft-center/[id]?tab=live
 *  - /league-recaps/[id] -> News > My League              /news?tab=league&league=[id]
 *  - /portfolio          -> Home's Standing section       /leagues#standing
 *  - /college-scouting   -> Players > Prospects           /players/[id]?tab=prospects (needs a league; see that page)
 */
export type RetiredLeagueSegment = "alerts" | "live-draft" | "league-recaps";

export function retiredRouteTarget(segment: RetiredLeagueSegment, leagueId: string, search: { get(key: string): string | null }): string {
  const id = encodeURIComponent(leagueId);
  const name = search.get("name") ?? "";
  const nameQuery = name ? `?name=${encodeURIComponent(name)}` : "";
  switch (segment) {
    case "alerts":
      return `/dashboard/${id}${nameQuery}#alerts`;
    case "live-draft":
      return `/draft-center/${id}${name ? `?name=${encodeURIComponent(name)}&` : "?"}tab=live`;
    case "league-recaps":
      return leagueRecapsHref(leagueId, name, { recaps: parseRecapsTab(search.get("tab")), week: parseRoundupWeek(search.get("week")) });
  }
}

/**
 * The href for a league page by its (possibly retired) route segment, so in-app links go straight to the new home
 * instead of through the redirect: Alerts -> Today#alerts, League Recaps -> News > My League.
 */
export function leagueSegmentHref(segment: string, leagueId: string, leagueName: string, anchor?: string | null): string {
  if (segment === "alerts") return retiredRouteTarget("alerts", leagueId, new URLSearchParams({ name: leagueName }));
  if (segment === "league-recaps") return leagueRecapsHref(leagueId, leagueName);
  return `/${segment}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}${anchor ? `#${anchor}` : ""}`;
}

/** Home: the league list with your standing across every league (formerly the Portfolio page). */
export const HOME_PATH = "/leagues";
export const PORTFOLIO_REDIRECT_TARGET = `${HOME_PATH}#standing`;

/** `/players/[id]?tab=prospects`, the home of College Scouting. */
export function prospectsHref(leagueId: string, leagueName: string): string {
  return `/players/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}&tab=prospects`;
}

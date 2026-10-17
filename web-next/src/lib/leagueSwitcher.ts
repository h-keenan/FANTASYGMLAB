/**
 * Swaps the league-id path segment in a pathname, keeping every other
 * segment — so switching leagues from a league-scoped page (e.g.
 * /waivers/OLD_ID) lands back on that same page with the new league
 * (/waivers/NEW_ID) instead of always bouncing to /dashboard/NEW_ID.
 *
 * coridian_, 2026-10-17: "when you switch leagues on a certain page, it
 * should stay on that page."
 */
export function swapLeagueIdInPath(pathname: string, currentLeagueId: string, newLeagueId: string): string {
  const encodedCurrentId = encodeURIComponent(currentLeagueId);
  const segments = pathname.split("/");
  const leagueSegmentIndex = segments.indexOf(encodedCurrentId);
  if (leagueSegmentIndex === -1) {
    return `/dashboard/${encodeURIComponent(newLeagueId)}`;
  }
  return [...segments.slice(0, leagueSegmentIndex), encodeURIComponent(newLeagueId), ...segments.slice(leagueSegmentIndex + 1)].join(
    "/",
  );
}

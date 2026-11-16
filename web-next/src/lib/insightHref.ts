import { leagueSegmentHref } from "@/lib/retiredRoutes";
import { insightAnchor, insightTarget, type InsightKey } from "@/lib/insightLinks";

/** Web URL for an insight: the page (lib/insightLinks.ts decides which), the league query, and the section anchor. */
export function insightHref(key: InsightKey, league: { id: string; name: string }): string {
  const { page } = insightTarget(key);
  const anchor = insightAnchor(key);
  return leagueSegmentHref(page, league.id, league.name, anchor);
}

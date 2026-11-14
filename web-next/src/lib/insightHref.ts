import { insightAnchor, insightTarget, type InsightKey } from "@/lib/insightLinks";

/** Web URL for an insight: the page (lib/insightLinks.ts decides which), the league query, and the section anchor. */
export function insightHref(key: InsightKey, league: { id: string; name: string }): string {
  const { page } = insightTarget(key);
  const anchor = insightAnchor(key);
  return `/${page}/${encodeURIComponent(league.id)}?name=${encodeURIComponent(league.name)}${anchor ? `#${anchor}` : ""}`;
}

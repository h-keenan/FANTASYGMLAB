import type { NavDestination } from "@/lib/navDestinations";
import { splitMoreByBar } from "@/lib/pageFamilies";

/** The league part of the More sheet: pages the bottom bar does NOT show first, then every page it does as one "Sections" group. */
export function moreLeagueGroups(destinations: readonly NavDestination[]): { title: string; rows: NavDestination[] }[] {
  const { lead, sections } = splitMoreByBar(destinations.map((d) => ({ d, key: d.key ?? "" })));
  return [
    { title: "League tools", rows: lead.map((x) => x.d) },
    { title: "Sections", rows: sections.map((x) => x.d) },
  ].filter((g) => g.rows.length > 0);
}

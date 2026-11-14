import { PillRow } from "@/components/PillRow";
import { activePageTab, pageTabFamily, type PageTabFamilyKey } from "@/lib/pageFamilies";
import type { TabIconName } from "@/lib/tabIcons";

/**
 * The top tab strip of a consolidated page family (lib/pageFamilies.ts): Trades (Hub / Finder / Analyzer / History),
 * Team (Roster / Players / Waivers / Matchup), League (Rankings / Recaps / Games). Every tab keeps its own route, so
 * old URLs and deep links keep working untouched; this strip is rendered at the top of each member page. Built on the
 * shared PillRow in its `glass` look (sticky, scroll-snap, count badges via `counts`). Web-only adapter: the app's
 * tab strip is components/SegmentedTabBar.tsx over the same lib/pageFamilies.ts.
 */
export function PageTabBar({
  family,
  active,
  leagueId,
  leagueName,
  counts,
}: {
  family: PageTabFamilyKey;
  /** A tab key from lib/pageFamilies.ts (e.g. "trade_finder", "waivers"). */
  active: string;
  leagueId: string;
  leagueName: string;
  /** Optional count badge per tab key. */
  counts?: Record<string, number | undefined>;
}) {
  const def = pageTabFamily(family);
  const name = encodeURIComponent(leagueName);
  const id = encodeURIComponent(leagueId);
  const options = def.tabs.map((tab) => ({
    label: tab.label,
    value: tab.key,
    glyph: tab.glyph as TabIconName,
    count: counts?.[tab.key],
    // Trade History is account-wide: it takes the league as `?league=` so the shell keeps the league context.
    href: tab.segment === "trade-history" ? `/trade-history?league=${id}&name=${name}` : `/${tab.segment}/${id}?name=${name}`,
  }));
  return <PillRow glass sticky variant="scroll" ariaLabel={def.label} options={options} active={activePageTab(def, active)} />;
}

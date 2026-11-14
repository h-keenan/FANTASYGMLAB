"use client";

import { PillRow } from "@/components/PillRow";
import type { PillContextAction } from "@/lib/bottomNav";
import { useBottomPillContext } from "@/lib/useBottomPillContext";
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
  primary,
}: {
  family: PageTabFamilyKey;
  /** A tab key from lib/pageFamilies.ts (e.g. "trade_finder", "waivers"). */
  active: string;
  leagueId: string;
  leagueName: string;
  /** Optional count badge per tab key. */
  counts?: Record<string, number | undefined>;
  /** The page's one primary action, shown as the accent chip in the phone pill (the page keeps its own button elsewhere). */
  primary?: PillContextAction;
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
  const activeKey = activePageTab(def, active);
  // Phones (smart pill): the family tabs move INTO the bottom pill, so this strip steps aside there. Elsewhere it stays.
  const familyPrimary = primary ?? defaultFamilyPrimary(family, options);
  const pillOwnsTabs = useBottomPillContext({
    id: `family:${family}`,
    label: def.label,
    // Each tab is a route: the pill renders them as links (client navigation), so there is nothing to do on select.
    tabs: options.map((o) => ({ key: o.value, label: o.label, glyph: o.glyph, badge: o.count, href: o.href })),
    activeKey,
    onSelect: () => {},
    primary: familyPrimary,
  });
  if (pillOwnsTabs) return null;
  return <PillRow glass sticky variant="scroll" ariaLabel={def.label} options={options} active={activeKey} />;
}

/** Trades: "New trade" opens the Analyzer, the one place a trade starts from scratch. Other families register no primary. */
function defaultFamilyPrimary(family: PageTabFamilyKey, options: { value: string; href: string }[]): PillContextAction | undefined {
  if (family !== "trades") return undefined;
  const href = options.find((o) => o.value === "trade_analyzer")?.href;
  return href ? { key: "new-trade", label: "New trade", glyph: "trades", href, onPress: () => {} } : undefined;
}

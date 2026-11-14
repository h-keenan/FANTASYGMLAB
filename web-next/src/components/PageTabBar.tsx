"use client";

import { PillRow } from "@/components/PillRow";
import type { PillContextAction } from "@/lib/bottomNav";
import { activePageTab, pageTabFamily, type PageTabFamilyKey } from "@/lib/pageFamilies";
import { familyPillContext } from "@/lib/pageFamilyPill";
import type { TabIconName } from "@/lib/tabIcons";
import { useBottomPillContext, usePillState } from "@/lib/useBottomPillContext";

/**
 * The top tab strip of a consolidated page family (lib/pageFamilies.ts): Trades (Hub / Finder / Analyzer / History),
 * Team (Roster / Players / Waivers / Matchup), League (Rankings / Recaps / Games). Every tab keeps its own route, so
 * old URLs and deep links keep working untouched; this strip is rendered at the top of each member page. Built on the
 * shared PillRow in its `glass` look (sticky, scroll-snap, count badges via `counts`). Web-only adapter: the app's
 * tab strip is components/SegmentedTabBar.tsx over the same lib/pageFamilies.ts.
 *
 * Phones with the smart pill on screen: the family tabs live in the bottom pill (AppShellBar derives them from the
 * route, so they are there before this page renders), and this strip steps aside: one tab row total. The page still
 * registers its context here so the pill gets its counts and primary action.
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
  /** The page's one primary action, shown as the accent chip in the phone pill. */
  primary?: PillContextAction;
}) {
  const def = pageTabFamily(family);
  const ctx = familyPillContext(family, active, leagueId, leagueName, { counts, primary });
  useBottomPillContext(ctx);
  const { barPresent } = usePillState();
  if (barPresent) return null;
  const options = ctx.tabs.map((tab) => ({ label: tab.label, value: tab.key, glyph: tab.glyph as TabIconName, count: tab.badge, href: tab.href as string }));
  return <PillRow glass sticky variant="scroll" ariaLabel={def.label} options={options} active={activePageTab(def, active)} />;
}

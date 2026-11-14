import type { PillContext, PillContextAction } from "@/lib/bottomNav";
import { activePageTab, pageTabFamily, pageTabForSegment, type PageTabFamilyKey } from "@/lib/pageFamilies";
import type { TabIconName } from "@/lib/tabIcons";

/**
 * The smart-pill context of a page family (Team / Trades / League), built from lib/pageFamilies.ts. Used twice:
 * PageTabBar registers it (with the page's counts / primary), and AppShellBar derives it from the ROUTE alone, so the
 * pill shows the family tabs from the first frame of a navigation (before the page has loaded and rendered) and the
 * plain global tabs never flash between two pages of one family.
 */
export function familyPillContext(
  family: PageTabFamilyKey,
  active: string,
  leagueId: string,
  leagueName: string,
  opts: { counts?: Record<string, number | undefined>; primary?: PillContextAction } = {},
): PillContext {
  const def = pageTabFamily(family);
  const name = encodeURIComponent(leagueName);
  const id = encodeURIComponent(leagueId);
  const options = def.tabs.map((tab) => ({
    key: tab.key,
    label: tab.label,
    short: tab.short,
    glyph: tab.glyph as TabIconName,
    badge: opts.counts?.[tab.key],
    // Trade History is account-wide: it takes the league as `?league=` so the shell keeps the league context.
    href: tab.segment === "trade-history" ? `/trade-history?league=${id}&name=${name}` : `/${tab.segment}/${id}?name=${name}`,
  }));
  const analyzer = options.find((o) => o.key === "trade_analyzer");
  const primary =
    opts.primary ?? (family === "trades" && analyzer ? ({ key: "new-trade", label: "New trade", glyph: "trades", href: analyzer.href, onPress: () => {} } as PillContextAction) : undefined);
  return {
    id: `family:${family}`,
    label: def.label,
    // Each tab is a route: the pill renders them as links (client navigation), so there is nothing to do on select.
    tabs: options,
    activeKey: activePageTab(def, active),
    onSelect: () => {},
    primary,
  };
}

/** The family context a pathname implies (null outside the families or without a league). */
export function routeFamilyPillContext(pathname: string | null | undefined, leagueId: string | null, leagueName: string): PillContext | null {
  if (!leagueId) return null;
  const segment = (pathname || "").split("/").filter(Boolean)[0];
  const hit = pageTabForSegment(segment);
  return hit ? familyPillContext(hit.family.key, hit.tab.key, leagueId, leagueName) : null;
}

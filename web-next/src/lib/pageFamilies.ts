/**
 * Consolidated page families (docs/audits/2026-11-menu-consolidation.md): related pages are presented as tabs of one
 * page, with the tab strip at the top. Byte-identical lib twin (scripts/check_lib_twins.mjs): which pages belong to
 * which family, their tab labels/glyphs and the segment -> family lookup live here once, so web and app cannot drift.
 *
 * Each tab keeps its own route (`segment`), so every old URL keeps working and nothing needs a redirect; the strip is
 * simply rendered at the top of each member page. Platform adapters turn a tab into a URL / screen.
 * Pure data, no imports.
 */

export type PageTabFamilyKey = "trades" | "team" | "league";

export type PageTabDef = {
  /** Stable key, also the `active` value a page passes. */
  key: string;
  label: string;
  /** Short label for tight surfaces (the phone pill): "Hist." */
  short?: string;
  /** Tab glyph name (lib/tabIcons.ts). */
  glyph: string;
  /** Web route segment / nav-catalog page key that opens this tab. */
  segment: string;
};

export type PageTabFamily = {
  key: PageTabFamilyKey;
  /** Aria label of the strip. */
  label: string;
  /** The bottom-bar tab this family lights (lib/shellNav.ts keys). */
  shellTab: string;
  tabs: readonly PageTabDef[];
};

/* prettier-ignore */
export const PAGE_TAB_FAMILIES: readonly PageTabFamily[] = [
  { key: "trades", label: "Trades section", shellTab: "trades", tabs: [
    { key: "trade_hub", label: "Hub", glyph: "hub", segment: "trade-hub" },
    { key: "trade_finder", label: "Finder", glyph: "finder", segment: "trade-finder" },
    { key: "trade_analyzer", label: "Analyzer", glyph: "analyzer", segment: "trade-analyzer" },
    { key: "trade_history", label: "History", short: "Hist.", glyph: "history", segment: "trade-history" },
  ] },
  { key: "team", label: "Team section", shellTab: "team", tabs: [
    { key: "roster", label: "Roster", glyph: "roster", segment: "my-team" },
    { key: "players", label: "Players", glyph: "players", segment: "players" },
    { key: "waivers", label: "Waivers", glyph: "recommended", segment: "waivers" },
    { key: "matchup", label: "Matchup", glyph: "scores", segment: "matchup" },
  ] },
  { key: "league", label: "League section", shellTab: "league", tabs: [
    { key: "rankings", label: "Rankings", glyph: "standings", segment: "league-rankings" },
    { key: "recaps", label: "Recaps", glyph: "recaps", segment: "league-recaps" },
    { key: "games", label: "Games", glyph: "scores", segment: "games" },
  ] },
];

export function pageTabFamily(key: PageTabFamilyKey): PageTabFamily {
  return PAGE_TAB_FAMILIES.find((f) => f.key === key) as PageTabFamily;
}

/** The family and tab a route segment belongs to (null when the page is not part of a family). */
export function pageTabForSegment(segment: string | null | undefined): { family: PageTabFamily; tab: PageTabDef } | null {
  if (!segment) return null;
  for (const family of PAGE_TAB_FAMILIES) {
    const tab = family.tabs.find((t) => t.segment === segment);
    if (tab) return { family, tab };
  }
  return null;
}

/** Tab keys that exist in a family, so a page passing an unknown `active` still renders with the first tab lit. */
export function activePageTab(family: PageTabFamily, active: string): string {
  return family.tabs.some((t) => t.key === active) ? active : (family.tabs[0]?.key ?? "");
}

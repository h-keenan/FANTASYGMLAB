/**
 * THE navigation sheet's content: one grouping, one set of copy, read by every menu that lists destinations.
 * Web: components/NavSheet.tsx (the bottom bar's More button, the header Search icon and the GM orb all open it).
 * App: the GM orb sheet (mobile/src/components/GmOrb.tsx). Byte-identical twin: mobile/src/lib/navSheet.ts
 * (scripts/check_lib_twins.mjs enforces it); scripts/check_nav_sheet.mjs fails when a destination list is rendered outside the sheet.
 *
 * The grouping (decided 2026-11-17 after "the search menu looks different than the More menu", one list serving both):
 *   1. <league name>  the core league pages (Today, My Team, Matchup, Waivers, League Rankings, Players); only inside a league
 *   2. GM Tools       Trade Hub, GM Plan, Draft, Commissioner; only inside a league
 *   3. General        Your leagues, Fantasy Sim, News, Community
 *   4. Account        Pro / Manage subscription, Account, and (founder sessions only) Founder Analytics
 * Order, labels, subtitles, Pro flags and tabs come from lib/navCatalog.ts (the one page list); rows carry the platform's own
 * path/route, glyph and accent. The bottom bar's own tabs are NOT split out: More and Search show the same full list, so the
 * answer to "where is X" never depends on which button opened the sheet.
 *
 * Pure data, no imports, so it runs under node:test and vitest alike.
 */

export type NavSheetGroupId = "league" | "tools" | "general" | "account";

export interface NavSheetGroup<T> {
  id: NavSheetGroupId;
  title: string;
  rows: T[];
}

export const NAV_SHEET_TITLE = "Where to go";
export const NAV_SHEET_NO_LEAGUE_NOTE = "Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.";

/** Placeholder and accessible name of the sheet's search field (players are searchable only inside a league). */
export function navSheetSearchCopy(hasLeague: boolean): { placeholder: string; label: string } {
  return hasLeague
    ? { placeholder: "Search where to go or a player", label: "Search destinations and players" }
    : { placeholder: "Search where to go", label: "Search destinations" };
}

export function navSheetNoMatch(hasLeague: boolean, query: string): string {
  return `${hasLeague ? "No destinations or players match" : "No destinations match"} “${query.trim()}”.`;
}

export interface NavSheetInput<T> {
  /** The selected league's name, or null outside a league (the league groups are then omitted). */
  leagueName: string | null;
  core: readonly T[];
  tools: readonly T[];
  general: readonly T[];
  account: readonly T[];
}

/** The sheet's groups in order; a group with no rows is dropped. */
export function navSheetGroups<T>(input: NavSheetInput<T>): NavSheetGroup<T>[] {
  const inLeague = input.leagueName !== null;
  const groups: NavSheetGroup<T>[] = [
    { id: "league", title: input.leagueName || "League", rows: inLeague ? [...input.core] : [] },
    { id: "tools", title: "GM Tools", rows: inLeague ? [...input.tools] : [] },
    { id: "general", title: "General", rows: [...input.general] },
    { id: "account", title: "Account", rows: [...input.account] },
  ];
  return groups.filter((g) => g.rows.length > 0);
}

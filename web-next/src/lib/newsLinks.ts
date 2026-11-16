import type { RecapsTab } from "@/lib/pageTabs";

/**
 * News is one destination with two tabs (NFL / My League; 2026-11-16 nav consolidation). League Recaps became the My League
 * tab, so every old League Recaps link (push deep links, the roundup alert card, the retired /league-recaps route) is built
 * here. News is account-wide, so the league rides along as `?league=` (the shell keeps the league context from it).
 */
export type NewsTab = "nfl" | "league";

export function parseNewsTab(value: string | null | undefined): NewsTab {
  return value === "league" ? "league" : "nfl";
}

export function leagueRecapsHref(leagueId: string, leagueName: string, opts: { recaps?: RecapsTab; week?: number } = {}): string {
  const query = new URLSearchParams({ tab: "league", league: leagueId });
  if (leagueName) query.set("name", leagueName);
  if (opts.recaps && opts.recaps !== "recaps") query.set("recaps", opts.recaps);
  if (opts.week) query.set("week", String(opts.week));
  return `/news?${query.toString()}`;
}

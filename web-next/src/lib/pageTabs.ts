// `?tab=` values for pages whose tabs the GM orb can open directly
// (navDestinations.ts `tabs`). Kept out of the page components so a page
// route can parse its param without importing the whole component.
export type WaiverTab = "recommended" | "explore" | "watchlist";
export type GamesTab = "sim" | "pickem";
export type RecapsTab = "recaps" | "history" | "storylines" | "roundup";

export function parseWaiverTab(value: string | null | undefined): WaiverTab | undefined {
  return value === "recommended" || value === "explore" || value === "watchlist" ? value : undefined;
}

export function parseGamesTab(value: string | null | undefined): GamesTab | undefined {
  return value === "sim" || value === "pickem" ? value : undefined;
}

export function parseRecapsTab(value: string | null | undefined): RecapsTab | undefined {
  return value === "recaps" || value === "history" || value === "storylines" || value === "roundup" ? value : undefined;
}

/** `?week=` for the Roundup tab (a push deep link carries it). */
export function parseRoundupWeek(value: string | null | undefined): number | undefined {
  const week = Number(value);
  return Number.isInteger(week) && week > 0 && week <= 30 ? week : undefined;
}

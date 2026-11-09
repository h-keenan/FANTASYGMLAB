// `?tab=` values for pages whose tabs the GM orb can open directly
// (navDestinations.ts `tabs`). Kept out of the page components so a page
// route can parse its param without importing the whole component.
export type WaiverTab = "recommended" | "explore" | "watchlist";
export type GamesTab = "sim" | "pickem";

export function parseWaiverTab(value: string | null | undefined): WaiverTab | undefined {
  return value === "recommended" || value === "explore" || value === "watchlist" ? value : undefined;
}

export function parseGamesTab(value: string | null | undefined): GamesTab | undefined {
  return value === "sim" || value === "pickem" ? value : undefined;
}

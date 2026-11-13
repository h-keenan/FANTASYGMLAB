/**
 * Central tab-icon registry: one semantic name per tab glyph, mapped to the
 * outline Ionicons glyph the mobile app already uses everywhere. Web renders
 * the same Ionicons SVG paths (components/TabGlyph.tsx), mobile renders the
 * Ionicons font glyph (components/TabIcon.tsx), so a tab reads as the same
 * icon on both platforms. Mirrors the navCatalog pattern: this file is a
 * byte-identical lib twin (scripts/check_lib_twins.mjs), so adding or
 * changing a tab icon is one edit that lands on both.
 *
 * Call sites pass `glyph: "<name>"` on a tab option; they never name an
 * Ionicons glyph directly.
 */
export const TAB_ICONS = {
  // Fantasy Sim primary tabs
  home: "home-outline",
  team: "people-outline",
  players: "person-outline",
  trades: "swap-horizontal-outline",
  league: "trophy-outline",
  more: "ellipsis-horizontal-circle-outline",
  // Trades section
  hub: "grid-outline",
  finder: "search-outline",
  analyzer: "analytics-outline",
  history: "time-outline",
  // Generic section tabs
  overview: "layers-outline",
  picks: "ticket-outline",
  scouting: "telescope-outline",
  core: "shield-checkmark-outline",
  watching: "eye-outline",
  watchlist: "bookmark-outline",
  // Waivers
  recommended: "sparkles-outline",
  explore: "compass-outline",
  addDrop: "add-circle-outline",
  // Player profile
  stats: "stats-chart-outline",
  trends: "trending-up-outline",
  schedule: "calendar-outline",
  career: "ribbon-outline",
  model: "hardware-chip-outline",
  news: "newspaper-outline",
  // League / recaps / season in review
  standings: "podium-outline",
  scores: "football-outline",
  feed: "list-outline",
  awards: "medal-outline",
  recaps: "newspaper-outline",
  roundup: "documents-outline",
  storylines: "book-outline",
  // Draft panels
  board: "grid-outline",
  queue: "list-outline",
  roster: "clipboard-outline",
  // Trades view / week
  week: "calendar-outline",
  inbox: "mail-outline",
  build: "construct-outline",
  // Sample league / games / portfolio / matchup
  dashboard: "speedometer-outline",
  today: "sunny-outline",
  sim: "dice-outline",
  pickem: "checkmark-done-outline",
  leagues: "layers-outline",
  exposure: "pie-chart-outline",
  suggested: "bulb-outline",
  actual: "checkbox-outline",
  prospects: "school-outline",
  mine: "person-circle-outline",
} as const;

export type TabIconName = keyof typeof TAB_ICONS;

/** The Ionicons glyph name behind a registry name (single lookup for both platforms). */
export function tabIconGlyph(name: TabIconName): (typeof TAB_ICONS)[TabIconName] {
  return TAB_ICONS[name];
}

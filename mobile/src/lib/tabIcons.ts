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
  scores: "american-football-outline",
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
  // Season Outlook sim inside Games (dice); the Fantasy Sim destination uses `fantasySim`.
  sim: "dice-outline",
  fantasySim: "custom-fantasy-sim",
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

/**
 * Custom (non-Ionicons) glyphs, 512 grid, 32 stroke, round caps/joins, tinted
 * by the current color. Platform-neutral element specs: web builds SVG markup
 * from them (components/TabGlyph.tsx), mobile draws them with react-native-svg
 * (components/TabIcon.tsx). `fill: true` elements are solid, the rest outlined.
 */
export interface CustomGlyphElement {
  tag: "rect" | "path" | "circle";
  attrs: Record<string, string | number>;
  fill?: boolean;
}

export const CUSTOM_TAB_GLYPHS: Record<string, CustomGlyphElement[]> = {
  // Calendar with a play triangle: Fantasy Sim.
  "custom-fantasy-sim": [
    { tag: "rect", attrs: { x: 64, y: 96, width: 384, height: 352, rx: 48 } },
    { tag: "path", attrs: { d: "M64 208h384M160 48v80M352 48v80" } },
    { tag: "path", attrs: { d: "M224 272l96 56-96 56z" } },
  ],
};

export function isCustomTabGlyph(glyph: string): boolean {
  return Object.prototype.hasOwnProperty.call(CUSTOM_TAB_GLYPHS, glyph);
}

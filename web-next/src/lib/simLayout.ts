/**
 * Phone-layout rules for the Fantasy Sim game, shared by web and the app
 * (byte-identical twin). Pure helpers only: storage and rendering stay in each
 * platform's Collapsible. See docs/fantasy-sim-mobile-layout.md.
 */

/** Persisted open/closed state key for a collapsible section. */
import type { TabIconName } from "./tabIcons";

export const SIM_OPEN_KEY_PREFIX = "fgl:sim-open:";

export function simOpenKey(id: string): string {
  return `${SIM_OPEN_KEY_PREFIX}${id}`;
}

/** Parse a stored open flag; anything unrecognised falls back to the default. */
export function simParseOpen(raw: string | null | undefined, fallback: boolean): boolean {
  if (raw === "1") return true;
  if (raw === "0") return false;
  return fallback;
}

/** Rows shown before a "See all" expander on a phone-width list. */
export const SIM_PREVIEW_ROWS = 3;

/** The first `limit` rows, or all of them once expanded; reports how many are hidden. */
export function simPreview<T>(items: readonly T[], expanded: boolean, limit: number = SIM_PREVIEW_ROWS): { shown: T[]; hidden: number } {
  if (expanded || items.length <= limit) return { shown: [...items], hidden: 0 };
  return { shown: items.slice(0, limit), hidden: items.length - limit };
}

/** Label for a See all / Show less toggle. */
export function simSeeAllLabel(hidden: number, expanded: boolean, noun = "more"): string {
  if (expanded) return "Show less";
  return hidden > 0 ? `See all (${hidden} ${noun})` : "See all";
}

/** Window size for long lists (draft board, players): rows rendered per "Show more" step. */
export const SIM_WINDOW_STEP = 20;

export function simWindow<T>(items: readonly T[], visible: number): { shown: T[]; remaining: number } {
  const n = Math.max(0, Math.min(visible, items.length));
  return { shown: items.slice(0, n), remaining: items.length - n };
}

/** Review / home sub-views (segmented controls inside long pages). */
export const SIM_REVIEW_VIEWS = [
  { value: "overview", label: "Overview", glyph: "overview" },
  { value: "awards", label: "Awards", glyph: "awards" },
  { value: "stats", label: "Stats", glyph: "stats" },
  { value: "standings", label: "Standings", glyph: "standings" },
] as const;
export type SimReviewView = (typeof SIM_REVIEW_VIEWS)[number]["value"];

export const SIM_HOME_VIEWS = [
  { value: "week", label: "This week", glyph: "week" },
  { value: "league", label: "League", glyph: "league" },
] as const;
export type SimHomeView = (typeof SIM_HOME_VIEWS)[number]["value"];

/** Which Season in Review tab a section lives on (phone layout); unknown ids stay on Overview. */
const REVIEW_VIEW_BY_SECTION: Record<string, SimReviewView> = {
  grade: "overview",
  decisions: "overview",
  "champion-path": "overview",
  "your-path": "overview",
  journey: "overview",
  moves: "awards",
  swings: "awards",
  injuries: "awards",
  stats: "stats",
  leaders: "stats",
  "your-leaders": "stats",
  "closest-yours": "stats",
  "closest-league": "stats",
};

export function simReviewViewFor(sectionId: string): SimReviewView {
  return REVIEW_VIEW_BY_SECTION[sectionId] ?? "overview";
}

/** Sections that start collapsed on a phone (reference material, not the story). */
export const SIM_REVIEW_COLLAPSED_ON_PHONE: readonly string[] = ["champion-path", "your-path", "journey", "closest-yours", "closest-league", "your-leaders"];

// ---------------------------------------------------------------------------
// Trade builder: a position-grouped asset picker with room for a "Picks" group

/**
 * One group in the trade picker. Players come grouped by position; a later
 * draft-pick feature adds a group with `kind: "pick"` and the same shape, so
 * the picker needs no changes to show it.
 */
export interface SimAssetGroup<T> {
  key: string;
  label: string;
  kind: "player" | "pick";
  items: T[];
}

export const SIM_ASSET_ALL = "ALL";

/** Group assets by position in the league's position order; empty groups are dropped. */
export function simGroupByPosition<T extends { pos: string }>(items: readonly T[], order: readonly string[]): SimAssetGroup<T>[] {
  const groups: SimAssetGroup<T>[] = [];
  for (const pos of order) {
    const list = items.filter((item) => item.pos === pos);
    if (list.length) groups.push({ key: pos, label: pos, kind: "player", items: list });
  }
  const known = new Set(order);
  const rest = items.filter((item) => !known.has(item.pos));
  if (rest.length) groups.push({ key: "OTHER", label: "Other", kind: "player", items: rest });
  return groups;
}

/** Keep the chosen group (or all) and the rows whose name matches the search text. */
export function simFilterGroups<T extends { name: string }>(groups: readonly SimAssetGroup<T>[], filter: string, search: string): SimAssetGroup<T>[] {
  const needle = search.trim().toLowerCase();
  return groups
    .filter((group) => filter === SIM_ASSET_ALL || group.key === filter)
    .map((group) => ({ ...group, items: needle ? group.items.filter((item) => item.name.toLowerCase().includes(needle)) : group.items }))
    .filter((group) => group.items.length > 0);
}

/** Count and total model value of one side of an offer. */
export function simSideSummary(items: readonly { value: number }[]): { count: number; value: number } {
  return { count: items.length, value: Math.round(items.reduce((sum, item) => sum + (Number.isFinite(item.value) ? item.value : 0), 0)) };
}

/** Roster size after the trade against the limit: `over` > 0 means that many must be cut. */
export function simTradeFit(rosterSize: number, limit: number, giving: number, getting: number): { after: number; room: number; over: number } {
  const after = Math.max(0, rosterSize - giving + getting);
  return { after, room: Math.max(0, limit - after), over: Math.max(0, after - limit) };
}

// ---------------------------------------------------------------------------
// Auto-set best lineup: what changed

export interface SimLineupDiffSlot {
  slot: string;
  player: { id: string; name: string } | null;
}

export interface SimLineupDiff {
  swaps: { slot: string; out: string | null; in: string | null }[];
  /** Projected points gained (rounded to 0.1); null when either total is unknown. */
  gain: number | null;
}

/** Compare the lineup before and after an auto-set, slot by slot. */
export function simLineupDiff(before: readonly SimLineupDiffSlot[], after: readonly SimLineupDiffSlot[], beforeTotal?: number | null, afterTotal?: number | null): SimLineupDiff {
  const swaps: SimLineupDiff["swaps"] = [];
  after.forEach((next, index) => {
    const prev = before[index];
    const prevId = prev?.player?.id ?? null;
    const nextId = next.player?.id ?? null;
    if (prevId !== nextId) swaps.push({ slot: next.slot, out: prev?.player?.name ?? null, in: next.player?.name ?? null });
  });
  const gain = beforeTotal == null || afterTotal == null ? null : Math.round((afterTotal - beforeTotal) * 10) / 10;
  return { swaps, gain };
}

/** The toast for an auto-set: names the swap, or says the lineup is already optimal. */
export function simAutoSetMessage(diff: SimLineupDiff): string {
  if (diff.swaps.length === 0) return "Lineup is optimal";
  const gain = diff.gain != null && diff.gain > 0 ? `, +${diff.gain.toFixed(1)} proj` : "";
  if (diff.swaps.length === 1) {
    const [swap] = diff.swaps;
    return swap.out && swap.in ? `Swapped ${swap.out} for ${swap.in}${gain}` : `Updated your ${swap.slot} slot${gain}`;
  }
  return `Made ${diff.swaps.length} lineup swaps${gain}`;
}

// ---------------------------------------------------------------------------
// Always-reachable action bar

export interface SimAdvanceState {
  /** "Wk 4 \u2192 5" or "Play round". */
  label: string;
  blocked: boolean;
  /** Why Advance is disabled (null when it is not). */
  reason: string | null;
}

/** Whether the bar's Advance button is available, and the reason when it is not. */
export function simAdvanceState(
  game: { phase?: string; week: number; pending?: { cuts_needed?: number } | null },
  emptySlots: number,
): SimAdvanceState {
  const label = game.phase === "playoffs" ? "Play round" : `Wk ${game.week} \u2192 ${game.week + 1}`;
  const cuts = game.pending?.cuts_needed ?? 0;
  if (cuts > 0) return { label, blocked: true, reason: `Cut ${cuts} player${cuts === 1 ? "" : "s"} first` };
  if (emptySlots > 0) return { label, blocked: true, reason: `Fill ${emptySlots} empty slot${emptySlots === 1 ? "" : "s"}` };
  return { label, blocked: false, reason: null };
}

/** Bottom clearance (rem) page content needs so the fixed bar and the floating GM orb never cover the last row. */
export const SIM_BOTTOM_CLEARANCE_BAR_REM = 8.5;
export const SIM_BOTTOM_CLEARANCE_ORB_REM = 6;

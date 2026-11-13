/**
 * Pure logic for the shared trade piece picker (the "sheet picker"): filter
 * model, selection state machine and summaries. No React and no platform
 * imports, so this file is a byte-identical twin of
 * mobile/src/lib/tradeSheetPicker.ts (keep them in sync).
 *
 * The picker works on generic items (`kind: "player" | "pick"`), so the main
 * Trade Analyzer, the multi-team builder and the Fantasy Sim trade builder
 * all drive the same sheet.
 *
 * Flow: tap a side -> sheet opens with that side's pool -> toggle rows (and
 * optionally set filters, which only take effect on Apply) -> "Add N to
 * trade" commits the whole selection at once. Closing without committing
 * discards the changes.
 */

export type SheetKind = "player" | "pick";
export type SheetTab = "players" | "picks";
export type SheetCondition = "healthy" | "injured" | "bye" | "rookie";

export const SHEET_CONDITIONS: { value: SheetCondition; label: string }[] = [
  { value: "healthy", label: "Healthy" },
  { value: "injured", label: "Injured" },
  { value: "bye", label: "On bye" },
  { value: "rookie", label: "Rookie" },
];

export interface SheetItem<T = unknown> {
  /** `${kind}:${id}`, unique across kinds. */
  key: string;
  kind: SheetKind;
  id: string;
  /** Player name or pick label. */
  label: string;
  position: string | null;
  team: string | null;
  age: number | null;
  /** Trade value (already on the display scale), null when unknown. */
  value: number | null;
  conditions: SheetCondition[];
  /** Photo lookup id for players (null shows initials). */
  photoId?: string | null;
  tier?: string | null;
  injury?: string | null;
  /** Small second line (pick range, owner, etc.). */
  detail?: string | null;
  /** Draft round / overall pick number for picks (drives the shared pick row). */
  round?: number | null;
  pickNo?: number | null;
  /** Pick grouping (season/round), used for section headers. */
  group?: string | null;
  /** The caller's own object, handed back untouched. */
  ref?: T;
}

export interface SheetFilters {
  positions: string[];
  conditions: SheetCondition[];
}

export const EMPTY_FILTERS: SheetFilters = { positions: [], conditions: [] };

export function itemKey(kind: SheetKind, id: string): string {
  return `${kind}:${id}`;
}

/** Condition tags for a player from the fields the app already carries. */
export function conditionsFor(input: {
  injuryStatus?: string | null;
  status?: string | null;
  age?: number | null;
  rookie?: boolean | null;
  bye?: boolean | null;
}): SheetCondition[] {
  const out: SheetCondition[] = [];
  const injury = (input.injuryStatus ?? "").trim().toLowerCase();
  const status = (input.status ?? "").trim().toLowerCase();
  const injured = injury !== "" && injury !== "active" && injury !== "healthy";
  const bye = Boolean(input.bye) || status === "bye";
  if (injured) out.push("injured");
  if (bye) out.push("bye");
  if (!injured && !bye) out.push("healthy");
  const rookie = input.rookie ?? (input.age != null && input.age <= 22);
  if (rookie) out.push("rookie");
  return out;
}

export function filtersEmpty(filters: SheetFilters): boolean {
  return filters.positions.length === 0 && filters.conditions.length === 0;
}

export function activeFilterCount(filters: SheetFilters): number {
  return filters.positions.length + filters.conditions.length;
}

function toggled<V>(list: V[], value: V): V[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Positions present in the pool, in a stable football order. */
const POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB"];
export const FLEX_POSITIONS = ["RB", "WR", "TE"];

/** Position chips for the filter panel. `flex` adds a FLEX chip (RB / WR / TE) after the real positions, for leagues that start a flex slot. */
export function positionsFor(items: SheetItem[], flex = false): string[] {
  const seen = new Set<string>();
  for (const item of items) if (item.kind === "player" && item.position) seen.add(item.position.toUpperCase());
  const sorted = [...seen].sort((a, b) => {
    const ia = POSITION_ORDER.indexOf(a);
    const ib = POSITION_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  if (flex && sorted.some((pos) => FLEX_POSITIONS.includes(pos))) {
    const lastFlexIndex = Math.max(...FLEX_POSITIONS.map((pos) => sorted.indexOf(pos)));
    sorted.splice(lastFlexIndex + 1, 0, "FLEX");
  }
  return sorted;
}

/** Items for the tab, narrowed by search and filters. Filters apply to players; picks only follow the search. */
export function filterSheetItems<T>(items: SheetItem<T>[], opts: { tab: SheetTab; query: string; filters: SheetFilters }): SheetItem<T>[] {
  const kind: SheetKind = opts.tab === "picks" ? "pick" : "player";
  const query = opts.query.trim().toLowerCase();
  return items.filter((item) => {
    if (item.kind !== kind) return false;
    if (query && !`${item.label} ${item.team ?? ""} ${item.position ?? ""}`.toLowerCase().includes(query)) return false;
    if (kind === "pick") return true;
    if (opts.filters.positions.length) {
      const pos = (item.position ?? "").toUpperCase();
      const flex = opts.filters.positions.includes("FLEX") && FLEX_POSITIONS.includes(pos);
      if (!flex && !opts.filters.positions.includes(pos)) return false;
    }
    if (opts.filters.conditions.length && !opts.filters.conditions.some((c) => item.conditions.includes(c))) return false;
    return true;
  });
}

export interface SheetState {
  tab: SheetTab;
  query: string;
  /** Filters in effect (set only by Apply). */
  filters: SheetFilters;
  /** The filter panel's working copy; null while the panel is closed. */
  draft: SheetFilters | null;
  /** Selected item keys, in the order they were picked. */
  selected: string[];
}

export type SheetAction =
  | { type: "tab"; tab: SheetTab }
  | { type: "query"; query: string }
  | { type: "openFilters" }
  | { type: "closeFilters" }
  | { type: "draftPosition"; position: string }
  | { type: "draftCondition"; condition: SheetCondition }
  | { type: "clearDraft" }
  | { type: "applyFilters" }
  | { type: "toggle"; key: string; max?: number }
  | { type: "remove"; key: string }
  | { type: "clearSelection" };

export function initialSheetState(selected: string[] = [], tab: SheetTab = "players", filters: SheetFilters = EMPTY_FILTERS): SheetState {
  return { tab, query: "", filters: { positions: [...filters.positions], conditions: [...filters.conditions] }, draft: null, selected: [...selected] };
}

export function sheetReducer(state: SheetState, action: SheetAction): SheetState {
  switch (action.type) {
    case "tab":
      return state.tab === action.tab ? state : { ...state, tab: action.tab, draft: null };
    case "query":
      return { ...state, query: action.query };
    case "openFilters":
      return { ...state, draft: { positions: [...state.filters.positions], conditions: [...state.filters.conditions] } };
    case "closeFilters":
      return { ...state, draft: null };
    case "draftPosition":
      return state.draft ? { ...state, draft: { ...state.draft, positions: toggled(state.draft.positions, action.position) } } : state;
    case "draftCondition":
      return state.draft ? { ...state, draft: { ...state.draft, conditions: toggled(state.draft.conditions, action.condition) } } : state;
    case "clearDraft":
      return state.draft ? { ...state, draft: EMPTY_FILTERS } : state;
    case "applyFilters":
      return state.draft ? { ...state, filters: state.draft, draft: null } : state;
    case "toggle": {
      if (state.selected.includes(action.key)) return { ...state, selected: state.selected.filter((k) => k !== action.key) };
      if (action.max != null && state.selected.length >= action.max) return state;
      return { ...state, selected: [...state.selected, action.key] };
    }
    case "remove":
      return { ...state, selected: state.selected.filter((k) => k !== action.key) };
    case "clearSelection":
      return { ...state, selected: [] };
    default:
      return state;
  }
}

/** Selected items in pick order; keys no longer in the pool are dropped. */
export function selectedItems<T>(items: SheetItem<T>[], keys: string[]): SheetItem<T>[] {
  const byKey = new Map(items.map((item) => [item.key, item]));
  return keys.map((key) => byKey.get(key)).filter((item): item is SheetItem<T> => Boolean(item));
}

export interface SheetSummary {
  count: number;
  players: number;
  picks: number;
  total: number;
}

export function summarizeItems(items: SheetItem[]): SheetSummary {
  return {
    count: items.length,
    players: items.filter((i) => i.kind === "player").length,
    picks: items.filter((i) => i.kind === "pick").length,
    total: items.reduce((sum, i) => sum + (i.value ?? 0), 0),
  };
}

/** Footer button label: "Add 3 to trade", "Update trade" when only removing, "Done" when nothing changed. */
export function applyLabel(selected: string[], initial: string[]): string {
  const sameSet = selected.length === initial.length && selected.every((k) => initial.includes(k));
  if (sameSet) return "Done";
  if (selected.length === 0) return "Clear this side";
  return initial.length === 0 ? `Add ${selected.length} to trade` : `Update trade (${selected.length})`;
}

/** One-line description of the filters in effect, e.g. "RB, WR · Injured". */
export function filterSummary(filters: SheetFilters): string {
  const parts: string[] = [];
  if (filters.positions.length) parts.push(filters.positions.join(", "));
  if (filters.conditions.length) parts.push(filters.conditions.map((c) => SHEET_CONDITIONS.find((o) => o.value === c)?.label ?? c).join(", "));
  return parts.join(" · ");
}

/**
 * Group picks by their `group` (season) while keeping order; players come back
 * as one unnamed group. Pick groups sort by label (earliest season first) and
 * their picks by round, so a pool in any order reads year then round.
 */
export function groupSheetItems<T>(items: SheetItem<T>[]): { key: string; label: string; items: SheetItem<T>[] }[] {
  const groups: { key: string; label: string; items: SheetItem<T>[] }[] = [];
  for (const item of items) {
    const label = item.group ?? "";
    let group = groups.find((g) => g.label === label);
    if (!group) {
      group = { key: label || "all", label, items: [] };
      groups.push(group);
    }
    group.items.push(item);
  }
  if (items.some((i) => i.kind === "pick")) {
    groups.sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
    for (const group of groups) group.items.sort((a, b) => (a.round ?? 99) - (b.round ?? 99));
  }
  return groups;
}

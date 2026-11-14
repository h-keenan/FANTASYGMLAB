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

/** The position a lineup slot label needs ("WR2" -> "WR", "FLEX" -> "RB, WR or TE"), for plain-words messages. */
export function simSlotNeed(label: string): string {
  const base = label.replace(/\d+$/, "");
  if (base === "FLEX") return "RB, WR or TE";
  if (base === "WRRB_FLEX") return "RB or WR";
  if (base === "SUPERFLEX") return "QB, RB, WR or TE";
  return base;
}

/**
 * The toast for an auto-set. The swaps come first; then anything auto-set could NOT fix is said plainly
 * (an empty slot means no eligible player is on the roster; a bye/out starter means nothing healthier fits),
 * so "optimal" is only claimed for a lineup that has no empty slot and no bye/out starter.
 */
export function simAutoSetMessage(diff: SimLineupDiff, issues?: { empty: readonly string[]; zero: readonly SimZeroStarter[] }): string {
  const empty = issues?.empty ?? [];
  const zero = issues?.zero ?? [];
  const unfixed = [
    ...empty.map((label) => `No ${simSlotNeed(label)} on your roster to start in ${label}. Claim one from the Players tab.`),
    ...zero.map((z) => `${z.name} (${z.label}) is ${z.reason === "bye" ? "on a bye" : "out"} and no healthier player fits.`),
  ];
  const tail = unfixed.length > 0 ? ` ${unfixed.join(" ")}` : "";
  if (diff.swaps.length === 0) return unfixed.length > 0 ? `Nothing to swap.${tail}` : "Lineup is optimal";
  const gain = diff.gain != null && diff.gain > 0 ? `, +${diff.gain.toFixed(1)} proj` : "";
  let head: string;
  if (diff.swaps.length === 1) {
    const [swap] = diff.swaps;
    head = swap.out && swap.in ? `Swapped ${swap.out} for ${swap.in}${gain}` : `Updated your ${swap.slot} slot${gain}`;
  } else {
    head = `Made ${diff.swaps.length} lineup swaps${gain}`;
  }
  return unfixed.length > 0 ? `${head}.${tail}` : head;
}

// ---------------------------------------------------------------------------
// Always-reachable action bar

export interface SimAdvanceState {
  /** "Wk 4 \u2192 5" or "Play round". */
  label: string;
  /** True only for an illegal state (roster over the limit). Everything else is a warning. */
  blocked: boolean;
  /** Why Advance is disabled (null when it is not). */
  reason: string | null;
  /** Soft warning shown above the bar; Advance stays enabled but asks to confirm. */
  warning: string | null;
  /** Confirm-dialog copy shown when the user taps Advance with a warning (null: advance straight away). */
  confirm: string | null;
}

/**
 * Labels for the empty starter slots ("WR2"): a position that appears more than
 * once in the lineup is numbered so the user can tell which slot is empty.
 */
export function simEmptySlotLabels(slots: readonly { slot: string; player?: unknown | null }[]): string[] {
  const total: Record<string, number> = {};
  for (const s of slots) total[s.slot] = (total[s.slot] ?? 0) + 1;
  const seen: Record<string, number> = {};
  const out: string[] = [];
  for (const s of slots) {
    seen[s.slot] = (seen[s.slot] ?? 0) + 1;
    if (!s.player) out.push(total[s.slot] > 1 ? `${s.slot}${seen[s.slot]}` : s.slot);
  }
  return out;
}

/** A starter who is in the lineup but will score 0 this week (bye or out). */
export interface SimZeroStarter {
  label: string;
  name: string;
  reason: "bye" | "out";
}

/**
 * What the Advance bar warns about, derived ONLY from the current authoritative
 * lineup response: `empty` comes from the slots (a slot with no player), `zero`
 * from the response's bye/out warnings matched to the player actually sitting in a
 * slot. A filled slot can therefore never be reported as empty.
 */
export function simLineupIssues(
  slots: readonly { slot: string; player?: { id?: string; name?: string } | null }[],
  warnings: readonly { code: string; player_id?: string | null }[] = [],
): { empty: string[]; zero: SimZeroStarter[] } {
  const total: Record<string, number> = {};
  for (const s of slots) total[s.slot] = (total[s.slot] ?? 0) + 1;
  const seen: Record<string, number> = {};
  const zero: SimZeroStarter[] = [];
  for (const s of slots) {
    seen[s.slot] = (seen[s.slot] ?? 0) + 1;
    const label = total[s.slot] > 1 ? `${s.slot}${seen[s.slot]}` : s.slot;
    const player = s.player;
    if (!player) continue;
    const hit = warnings.find((w) => (w.code === "bye" || w.code === "out") && w.player_id && w.player_id === player.id);
    if (hit) zero.push({ label, name: player.name ?? "Your starter", reason: hit.code as "bye" | "out" });
  }
  return { empty: simEmptySlotLabels(slots), zero };
}

/**
 * Whether the bar's Advance button is available. An empty starting slot is a
 * warning, never a block: claims are resolved at the START of Advance (before
 * lineups lock and games are scored) and the engine auto-fills empty slots from
 * the healthy bench, so a user with no legal fill must still be able to move on
 * (the slot scores 0). Only a roster over the limit blocks (cut is always possible).
 * `empty` is the empty slot labels (or just a count).
 */
export function simAdvanceState(
  game: { phase?: string; week: number; pending?: { cuts_needed?: number } | null },
  empty: number | readonly string[],
  zero: readonly SimZeroStarter[] = [],
): SimAdvanceState {
  const label = game.phase === "playoffs" ? "Play round" : `Wk ${game.week} \u2192 ${game.week + 1}`;
  const cuts = game.pending?.cuts_needed ?? 0;
  if (cuts > 0) return { label, blocked: true, reason: `Cut ${cuts} player${cuts === 1 ? "" : "s"} first`, warning: null, confirm: null };
  const names = typeof empty === "number" ? Array.from({ length: empty }, () => "A starting slot") : empty;
  if (names.length === 0 && zero.length === 0) return { label, blocked: false, reason: null, warning: null, confirm: null };
  const n = names.length;
  const who = n === 1 ? `${names[0]} is` : `${names.join(", ")} are`;
  const zeroConfirmWho = zero.map((z) => `${z.name} (${z.label}) ${z.reason === "bye" ? "is on a bye" : "is out"}`).join(", ");
  const zeroWarnWho = zero.map((z) => `${z.name} (${z.label}, ${z.reason === "bye" ? "bye" : "out"})`).join(", ");
  const emptyConfirm = n > 0 ? `${who} empty and will score 0 unless a healthy bench player fits.` : "";
  const zeroConfirm = zero.length > 0 ? `${zeroConfirmWho} and will score 0 unless you swap ${zero.length === 1 ? "him" : "them"}.` : "";
  const emptyWarning = n > 0 ? `${n} empty slot${n === 1 ? "" : "s"}: ${n === 1 ? names[0] : names.join(", ")} will score 0.` : "";
  const zeroWarning = zero.length > 0 ? `${zero.length} starter${zero.length === 1 ? "" : "s"} will score 0: ${zeroWarnWho}.` : "";
  return {
    label,
    blocked: false,
    reason: null,
    warning: `${[emptyWarning, zeroWarning].filter(Boolean).join(" ")} Claims process when you advance, before games are scored.`,
    confirm: `${[emptyConfirm, zeroConfirm].filter(Boolean).join(" ")} Advance anyway?`,
  };
}

/** Bottom clearance (rem) page content needs so the fixed bar and the floating GM orb never cover the last row. */
export const SIM_BOTTOM_CLEARANCE_BAR_REM = 8.5;
export const SIM_BOTTOM_CLEARANCE_ORB_REM = 6;

/** Header of the scoreboard pager: "Week 10", or "Semifinal · Week 15" in the playoffs (never "Week 10 · Week 10"). */
export function simScoreboardLabel(roundLabel: string, week: number): string {
  return roundLabel === `Week ${week}` ? roundLabel : `${roundLabel} · Week ${week}`;
}

export interface SimMatchupStatus {
  key: "final" | "upcoming";
  label: string;
  tone: "success" | "muted";
}

/** The status key of a matchup card: FINAL once scored, UPCOMING before. */
export function simMatchupStatus(game: { home_pts: number | null; away_pts: number | null; winner: string | null }): SimMatchupStatus {
  const played = game.home_pts != null && game.away_pts != null;
  return played ? { key: "final", label: "FINAL", tone: "success" } : { key: "upcoming", label: "UPCOMING", tone: "muted" };
}

/** Margin line for the matchup sheet: "Boom or Bust won by 12.4", "Tie", or "Not played yet". */
export function simMatchupMargin(game: { home: string; away: string; home_pts: number | null; away_pts: number | null }, names: Record<string, string>): string {
  if (game.home_pts == null || game.away_pts == null) return "Not played yet";
  const diff = Math.round((game.home_pts - game.away_pts) * 10) / 10;
  if (diff === 0) return "Tie";
  const winner = diff > 0 ? game.home : game.away;
  return `${names[winner] ?? "Team"} won by ${Math.abs(diff).toFixed(1)}`;
}

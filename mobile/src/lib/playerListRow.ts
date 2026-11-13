/**
 * Model + rules for the shared player-list row (`PlayerListRow`, the `list`
 * variant of the player card system; docs/player-card.md). Pure and
 * import-free, byte-identical twin of mobile/src/lib/playerListRow.ts.
 */
import type { ChipTone } from "./playerCard";

export type PlayerListDensity = "comfortable" | "compact";

/** Photo size and minimum tap height per density. `comfortable` is the default list row. */
export const PLAYER_LIST_DENSITY: Record<PlayerListDensity, { avatar: number; minHeight: number }> = {
  comfortable: { avatar: 40, minHeight: 44 },
  compact: { avatar: 32, minHeight: 36 },
};

/**
 * One labeled stat pill ("PROJ 10.8"). Every number in a list row carries its caption.
 * A stat with a `rating` is the player's Overall and renders as the shared OVR gauge
 * (OvrGauge, same ring, thresholds and colors as the Player Quick View hero), never as a plain pill.
 */
export interface PlayerListStat {
  key: string;
  label: string;
  value: string;
  tone?: ChipTone;
  /** Overall 1-99: render the OVR gauge instead of a text pill. */
  rating?: number | null;
  /** Tap-for-why registry key (lib/tapForWhyContent) that explains this stat, e.g. "trade_value". */
  why?: string;
}

/** A page-specific tag ("Hot streak", "Waiver target", "Owned by Taco Tuesday"). */
export interface PlayerListTag {
  key: string;
  label: string;
  tone?: ChipTone;
}

/** A piece of the muted second line: TEAM · Age 24 · Bye 7. */
export interface PlayerListMetaPart {
  key: string;
  text: string;
  tone?: ChipTone;
}

/** Fixed pill widths (px), so PROJ / OVR / TRADE VALUE / ADP / EDGE line up row after row. */
export const PLAYER_LIST_STAT_WIDTH: Record<string, number> = { proj: 66, ovr: 66, tval: 104, adp: 52, edge: 58 };
/** Column order. `metric` is the one 0-100 slot: the player's Overall (`ovr`) in lists, or `tval` (Trade value) on trade screens, never both. */
export const PLAYER_LIST_STAT_ORDER = ["proj", "metric", "adp", "edge"] as const;
/** Empty-slot widths by column (an empty `metric` slot reserves the Overall width). */
export const PLAYER_LIST_SLOT_WIDTH: Record<(typeof PLAYER_LIST_STAT_ORDER)[number], number> = { proj: 66, metric: 66, adp: 52, edge: 58 };

/** At most `max` tags are shown; the rest collapse into a "+N". */
export function limitPlayerListTags<T>(tags: T[], max = 2): { shown: T[]; extra: number } {
  if (tags.length <= max) return { shown: tags, extra: 0 };
  return { shown: tags.slice(0, max), extra: tags.length - max };
}

/** Stats in the fixed column order; unknown keys follow. A missing slot is null (kept as a gap so columns line up). */
export function orderPlayerListStats(stats: PlayerListStat[]): (PlayerListStat | null)[] {
  const byKey = new Map(stats.map((s) => [s.key, s]));
  const slotStat = (slot: (typeof PLAYER_LIST_STAT_ORDER)[number]) => (slot === "metric" ? (byKey.get("ovr") ?? byKey.get("tval") ?? null) : (byKey.get(slot) ?? null));
  const ordered: (PlayerListStat | null)[] = PLAYER_LIST_STAT_ORDER.map(slotStat);
  const known = new Set<string>(["proj", "ovr", "tval", "adp", "edge"]);
  for (const s of stats) if (!known.has(s.key)) ordered.push(s);
  // Drop trailing empty slots so a list without Edge does not reserve width for it.
  while (ordered.length > 0 && ordered[ordered.length - 1] === null) ordered.pop();
  return ordered;
}

/** Names longer than this drop one font size before they would ever truncate. */
export const PLAYER_LIST_LONG_NAME = 18;

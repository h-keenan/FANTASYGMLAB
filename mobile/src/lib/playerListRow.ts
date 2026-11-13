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

/** One labeled stat pill ("PROJ 10.8"). Every number in a list row carries its caption. */
export interface PlayerListStat {
  key: string;
  label: string;
  value: string;
  tone?: ChipTone;
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

/** Fixed pill widths (px), so PROJ / VAL / ADP / EDGE line up row after row. */
export const PLAYER_LIST_STAT_WIDTH: Record<string, number> = { proj: 66, val: 54, adp: 52, edge: 58 };
export const PLAYER_LIST_STAT_ORDER = ["proj", "val", "adp", "edge"] as const;

/** At most `max` tags are shown; the rest collapse into a "+N". */
export function limitPlayerListTags<T>(tags: T[], max = 2): { shown: T[]; extra: number } {
  if (tags.length <= max) return { shown: tags, extra: 0 };
  return { shown: tags.slice(0, max), extra: tags.length - max };
}

/** Stats in the fixed column order; unknown keys follow. Missing edge leaves its slot empty (null). */
export function orderPlayerListStats(stats: PlayerListStat[]): (PlayerListStat | null)[] {
  const byKey = new Map(stats.map((s) => [s.key, s]));
  const ordered: (PlayerListStat | null)[] = PLAYER_LIST_STAT_ORDER.map((k) => byKey.get(k) ?? null);
  const known = new Set<string>(PLAYER_LIST_STAT_ORDER);
  for (const s of stats) if (!known.has(s.key)) ordered.push(s);
  // Drop trailing empty slots so a list without Edge does not reserve width for it.
  while (ordered.length > 0 && ordered[ordered.length - 1] === null) ordered.pop();
  return ordered;
}

/** Names longer than this drop one font size before they would ever truncate. */
export const PLAYER_LIST_LONG_NAME = 18;

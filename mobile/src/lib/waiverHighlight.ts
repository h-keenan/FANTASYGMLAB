// Pure logic behind the Waivers `playerId` deep link (web: ?playerId= +
// HighlightTarget). Decides which tab holds the player and whether they are on
// the user's waiver list at all, so the screen never highlights a ghost.
export type WaiverHighlightTab = 'recommended' | 'explore';

interface HasId {
  player_id: string;
  position?: string | null;
}

export interface WaiverLists {
  priorityAdds: HasId[];
  stashCandidates: HasId[];
  watchlistCandidates: HasId[];
  faabTargets: HasId[];
  players: HasId[];
  idpPlayers?: HasId[];
  /** Premium gates the stash/depth/FAAB board; locked rows are not visible. */
  isPremium: boolean;
}

export type WaiverHighlightTarget =
  | { found: false }
  | {
      found: true;
      tab: WaiverHighlightTab;
      /** Explore position filter that makes the player visible. */
      position: string;
    };

const has = (list: HasId[] | undefined, id: string) => !!list?.some((p) => p.player_id === id);

/** True when the player is somewhere on the waiver screen (any list). */
export function isOnWaiverList(playerId: string | null | undefined, lists: WaiverLists): boolean {
  return locateWaiverPlayer(playerId, lists).found;
}

export function locateWaiverPlayer(playerId: string | null | undefined, lists: WaiverLists): WaiverHighlightTarget {
  const id = (playerId ?? '').trim();
  if (!id) return { found: false };
  const onRecommended =
    has(lists.priorityAdds, id) ||
    (lists.isPremium &&
      (has(lists.stashCandidates, id) || has(lists.watchlistCandidates, id) || has(lists.faabTargets, id)));
  if (onRecommended) return { found: true, tab: 'recommended', position: 'ALL' };
  if (has(lists.players, id)) return { found: true, tab: 'explore', position: 'ALL' };
  const idp = lists.idpPlayers?.find((p) => p.player_id === id);
  if (idp) return { found: true, tab: 'explore', position: idp.position || 'ALL' };
  return { found: false };
}

/** FlatList row for item `index` when laid out in `numColumns` columns. */
export function listRowIndex(index: number, numColumns: number): number {
  return Math.floor(index / Math.max(1, numColumns));
}

export const WAIVER_HIGHLIGHT_MS = 2800;

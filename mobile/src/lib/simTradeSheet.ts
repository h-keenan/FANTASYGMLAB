import { conditionsFor, itemKey, type SheetItem } from "./tradeSheetPicker";
import type { SimAssetGroup } from "./simLayout";

/** What the shared sheet picker needs from a sim asset (a SimGamePlayer, or a future pick row). */
export interface SimAssetLike {
  id: string;
  name: string;
  pos?: string;
  team?: string | null;
  age?: number | null;
  status?: string;
}

/**
 * Flatten the picker groups into the shared sheet picker's generic items,
 * keeping each group's `kind` (player or pick) so draft picks need no extra
 * wiring. `photo` maps a player to its photo id (null shows initials).
 */
export interface SimPickDescription {
  label: string;
  detail?: string | null;
  round?: number | null;
  /** Section header in the Picks tab, e.g. "2027 picks". */
  group?: string | null;
}

export function simGroupsToSheetItems<T extends SimAssetLike>(
  groups: readonly SimAssetGroup<T>[],
  photo: (item: T) => string | null,
  describePick?: (item: T) => SimPickDescription,
): SheetItem<T>[] {
  return groups.flatMap((group) =>
    group.items.map((item): SheetItem<T> => {
      const isPlayer = group.kind === "player";
      const pick = !isPlayer && describePick ? describePick(item) : null;
      return {
        key: itemKey(group.kind, item.id),
        kind: group.kind,
        id: item.id,
        label: pick?.label ?? item.name,
        position: isPlayer ? (item.pos ?? null) : null,
        team: isPlayer ? (item.team ?? null) : null,
        age: isPlayer ? (item.age ?? null) : null,
        // The sim's internal rating is never shown (it is the model's own number), so the picker gets no value.
        value: null,
        conditions: isPlayer ? conditionsFor({ injuryStatus: item.status === "out" ? "Out" : null, bye: item.status === "bye", age: item.age ?? null }) : [],
        photoId: isPlayer ? photo(item) : null,
        injury: isPlayer && item.status === "out" ? "Out" : null,
        group: isPlayer ? null : (pick?.group ?? group.label),
        detail: pick?.detail ?? null,
        round: pick?.round ?? null,
        ref: item,
      };
    }),
  );
}

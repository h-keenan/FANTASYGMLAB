import type { DraftPickAsset } from "@/lib/api";

/**
 * Pure grouping for the shared pick list (PickGroupList): season -> round ->
 * picks, plus the labels and default-open rule. Mobile mirrors this in
 * mobile/src/lib/pickGroups.ts; keep the two in sync.
 */

export interface PickRoundGroup {
  round: number;
  label: string;
  picks: DraftPickAsset[];
}

export interface PickSeasonGroup {
  season: number;
  label: string;
  count: number;
  rounds: PickRoundGroup[];
}

/** A round group with more picks than this starts collapsed. */
export const PICK_GROUP_OPEN_LIMIT = 3;

export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

export function roundLabel(round: number): string {
  return round > 0 ? `${ordinal(round)} round` : "Other picks";
}

/** Season asc, then round asc, then score desc. Unknown season/round sort last-bucketed as 0 -> "Future"/"Other". */
export function groupPicksForList(picks: DraftPickAsset[]): PickSeasonGroup[] {
  const bySeason = new Map<number, Map<number, DraftPickAsset[]>>();
  for (const pick of picks) {
    const season = pick.season ?? 0;
    const round = pick.round ?? 0;
    let rounds = bySeason.get(season);
    if (!rounds) bySeason.set(season, (rounds = new Map()));
    const bucket = rounds.get(round);
    if (bucket) bucket.push(pick);
    else rounds.set(round, [pick]);
  }
  return [...bySeason.entries()]
    .sort(([a], [b]) => (a || Infinity) - (b || Infinity))
    .map(([season, rounds]) => {
      const roundGroups = [...rounds.entries()]
        .sort(([a], [b]) => (a || Infinity) - (b || Infinity))
        .map(([round, list]) => ({
          round,
          label: roundLabel(round),
          picks: [...list].sort((x, y) => (y.score ?? 0) - (x.score ?? 0)),
        }));
      return {
        season,
        label: season ? String(season) : "Future",
        count: roundGroups.reduce((sum, group) => sum + group.picks.length, 0),
        rounds: roundGroups,
      };
    });
}

/** Compact one-line provenance: "Own pick" or "From Team X"; with the owner when browsing other teams. */
export function pickProvenance(pick: DraftPickAsset, opts: { showOwner?: boolean } = {}): string {
  const own = !pick.original_roster_id || pick.original_roster_id === pick.owner_roster_id;
  const base = own ? "Own" : `From ${pick.original_team_name || "another team"}`;
  return opts.showOwner && pick.owner_team_name ? `${pick.owner_team_name} · ${base}` : base;
}

/** Whether a round group starts open: short groups, the first group, or one holding a selected pick. */
export function roundGroupDefaultOpen(group: PickRoundGroup, isFirst: boolean, selectedIds?: ReadonlySet<string>): boolean {
  if (isFirst || group.picks.length <= PICK_GROUP_OPEN_LIMIT) return true;
  return Boolean(selectedIds && group.picks.some((pick) => selectedIds.has(pick.pick_id)));
}

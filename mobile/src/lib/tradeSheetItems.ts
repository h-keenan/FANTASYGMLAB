import type { DraftPickAsset, RankedPlayer } from './api';
import { conditionsFor, itemKey, type SheetItem } from './tradeSheetPicker';

/** A ranked player as a sheet-picker item (`ref` hands the player back). Mirrors web's tradeAnalyzerPresentation. */
export function playerToSheetItem(player: RankedPlayer): SheetItem<RankedPlayer> {
  return {
    key: itemKey('player', player.player_id),
    kind: 'player',
    id: player.player_id,
    label: player.name ?? 'Player',
    position: player.position,
    team: player.team,
    age: player.age,
    value: player.score,
    conditions: conditionsFor({ injuryStatus: player.injury_status, status: player.status, age: player.age }),
    photoId: player.player_id,
    tier: player.tier,
    injury: player.injury_status,
    ref: player,
  };
}

/** A draft pick as a sheet-picker item, grouped by season. */
export function pickToSheetItem(pick: DraftPickAsset): SheetItem<DraftPickAsset> {
  return {
    key: itemKey('pick', pick.pick_id),
    kind: 'pick',
    id: pick.pick_id,
    label: pick.label ?? 'Draft pick',
    position: null,
    team: null,
    age: null,
    value: pick.score,
    conditions: [],
    detail: [pick.projected_pick_range, pick.owner_team_name].filter(Boolean).join(' · ') || null,
    group: pick.season != null ? `${pick.season} picks` : null,
    round: pick.round,
    ref: pick,
  };
}

import type { PublicBoard, PublicPlayer } from "./publicValues";

/** A rookie page needs at least this many first-year players on the board to be worth showing or indexing. */
export const MIN_ROOKIES = 12;
export const ROOKIE_ROWS = 50;

export interface RookieRow {
  player: PublicPlayer;
  superflex: PublicPlayer | null;
}

/** First-year players (years_exp === 0) on the public 1QB board, best value first, with their Superflex row. */
export function rookieRows(oneQb: PublicBoard, superflex: PublicBoard | null): RookieRow[] {
  const sfById = new Map((superflex?.players ?? []).map((p) => [p.player_id, p]));
  return oneQb.players
    .filter((p) => p.years_exp === 0)
    .sort((a, b) => a.overall_rank - b.overall_rank)
    .slice(0, ROOKIE_ROWS)
    .map((player) => ({ player, superflex: sfById.get(player.player_id) ?? null }));
}

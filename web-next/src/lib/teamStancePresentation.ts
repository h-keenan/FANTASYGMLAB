/**
 * Team Situation (Revision 19) presentation helpers — pure formatting only.
 * The "Protected Players" checklist has no storage of its own (see
 * modules/team_stance_ui.py and mobile's TeamStanceScreen.tsx) — it reads/
 * writes GM Targets' existing `untouchable` flag directly. This file only
 * joins GET .../my-team's roster against GET .../gm-targets' untouchable
 * set, the same client-side join mobile's screen already does.
 */

import type { GmTarget, LineupPlayer } from "./api";

export interface ProtectRow {
  player: LineupPlayer;
  protected: boolean;
}

/** Starters + bench, deduped, each flagged by whether it's currently an
 * untouchable GM Target — same join mobile's TeamStanceScreen.tsx does in
 * its `load()`. */
export function buildProtectRows(
  starters: LineupPlayer[],
  bench: LineupPlayer[],
  targets: GmTarget[],
): ProtectRow[] {
  const protectedIds = new Set(targets.filter((t) => t.untouchable).map((t) => t.player_id));
  const seen = new Set<string>();
  const rows: ProtectRow[] = [];
  for (const player of [...starters, ...bench]) {
    if (seen.has(player.player_id)) continue;
    seen.add(player.player_id);
    rows.push({ player, protected: protectedIds.has(player.player_id) });
  }
  return rows;
}

/** Protected players lead, same "Protected Players" / "Rest of Roster"
 * split mobile's screen renders (TeamStanceScreen.tsx's protectedRows /
 * otherRows). */
export function splitProtectRows(rows: ProtectRow[]): { protectedRows: ProtectRow[]; otherRows: ProtectRow[] } {
  return {
    protectedRows: rows.filter((row) => row.protected),
    otherRows: rows.filter((row) => !row.protected),
  };
}

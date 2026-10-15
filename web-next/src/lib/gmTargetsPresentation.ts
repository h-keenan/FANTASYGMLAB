/**
 * GM Targets (Revision 11) presentation helpers — pure formatting only.
 * The watchlist itself (modules/gm_targets.py) is a thin preference table;
 * this page joins its rows against GET .../rankings for display, the same
 * client-side join mobile's GmTargetsScreen.tsx already does. No scoring,
 * ranking, or entitlement logic lives here.
 */

import type { GmTarget, RankedPlayer } from "./api";

export interface GmTargetRow {
  target: GmTarget;
  player: RankedPlayer | null;
}

/** GmTarget.source_surface already tells the story of *why* a player is on
 * this list. Merges both real callers across clients that write to this one
 * shared table: Streamlit web's Player Quick View ("player_quick_view") and
 * mobile's Player Detail ("player_detail"), plus Team Situation's "Protect"
 * checklist ("team_stance") and this page's own control ("gm_targets").
 * Matches modules/gm_targets_ui.py's TARGET_ORIGIN_LABELS and mobile's
 * TARGET_ORIGIN_LABEL. Unknown/legacy values render nothing rather than a
 * guess. */
const TARGET_ORIGIN_LABEL: Record<string, string> = {
  player_quick_view: "Added from Player Quick View",
  player_detail: "Added from Player Detail",
  team_stance: "Protected via Team Situation",
  gm_targets: "Added from GM Targets",
};

export function targetOriginLabel(sourceSurface: string | null | undefined): string | null {
  const key = (sourceSurface ?? "").trim();
  return key ? (TARGET_ORIGIN_LABEL[key] ?? null) : null;
}

/** The row's trailing context line: the real origin of this target when the
 * player matched the current rankings board, or an explicit "can't display
 * this one fully" note when it didn't (same fallback as mobile's
 * GmTargetsScreen.tsx — a saved target the rankings pool doesn't currently
 * carry, e.g. a since-retired/practice-squad player). */
export function targetContextLine(row: GmTargetRow): string | null {
  if (!row.player) return "Not on the current rankings board";
  return targetOriginLabel(row.target.source_surface);
}

/** Untouchable is the one real GM decision already encoded on a saved
 * target (GmTarget.untouchable, read directly by the trade engine) — group
 * by it so "who's protected from a trade" outranks "who am I just
 * watching," the same real backend distinction both modules/gm_targets_ui.py
 * and mobile's GmTargetsScreen.tsx group by. Sorted newest-first within each
 * group, matching both reference implementations. */
export function groupTargetRows(rows: GmTargetRow[]): { untouchable: GmTargetRow[]; watching: GmTargetRow[] } {
  const sorted = [...rows].sort((a, b) => (b.target.created_at ?? "").localeCompare(a.target.created_at ?? ""));
  return {
    untouchable: sorted.filter((row) => row.target.untouchable),
    watching: sorted.filter((row) => !row.target.untouchable),
  };
}

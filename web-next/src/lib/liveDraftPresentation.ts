/**
 * Live Draft (Revision 21) presentation helpers — pure display-only
 * transforms. Every value/rank/recommendation is already computed
 * server-side (GET .../leagues/{id}/live-draft/{draftId}, wrapping
 * modules/live_draft.py's build_live_draft_state verbatim). Nothing here
 * re-derives a score or a ranking.
 *
 * Rank movement is the one piece of display state that genuinely has no
 * server home: Streamlit's route keeps the previous poll's ranks in
 * st.session_state and diffs them into each row's `movement` field. This
 * stateless REST endpoint has no session, so it always reports
 * `movement: 0`, and the client instead keeps the previous poll's ranks in
 * memory (a plain object this page holds between polls) and diffs them
 * itself here — the same trivial (previous_rank - current_rank) arithmetic
 * modules/live_draft.py already does, not a new ranking computation.
 *
 * The ▲/▼ glyph convention and its +/-2 threshold mirror
 * modules/live_draft_ui.py's `_movement_label` exactly (the one canonical
 * rank-movement indicator this app uses everywhere — rankings.py's
 * recency_trend_display, player_compare.py, weekly_report_ui.py's
 * _movement_direction_badge_html — fixed to this glyph in PR #1067). Keep
 * this in sync with that convention, not re-invented per page.
 */

import type { LiveDraftRankingRow, LiveDraftTeamRow } from "./api";

export const LIVE_DRAFT_RANK_FILTERS = ["Overall", "QB", "RB", "WR", "TE", "Rookies", "Veterans"] as const;
export type LiveDraftRankFilter = (typeof LIVE_DRAFT_RANK_FILTERS)[number];

/** Veterans only appears as an option once the board actually has a
 * non-rookie in it — same guard modules/live_draft_ui.py's
 * _render_live_rankings applies before adding it to filter_options. */
export function liveDraftRankFilterOptions(rows: LiveDraftRankingRow[]): LiveDraftRankFilter[] {
  const hasVeteran = rows.some((row) => !row.is_rookie);
  const base: LiveDraftRankFilter[] = ["Overall", "QB", "RB", "WR", "TE", "Rookies"];
  return hasVeteran ? [...base, "Veterans"] : base;
}

export function filterLiveDraftRankings(
  rows: LiveDraftRankingRow[],
  filter: LiveDraftRankFilter,
): LiveDraftRankingRow[] {
  if (filter === "Overall") return rows;
  if (filter === "Rookies") return rows.filter((row) => row.is_rookie);
  if (filter === "Veterans") return rows.filter((row) => !row.is_rookie);
  return rows.filter((row) => (row.position || "").toUpperCase() === filter);
}

/** previous_rank - current_rank: positive means the player climbed the
 * board since the last poll (fewer picks away from being taken), negative
 * means they slid. Mirrors modules/live_draft.py's own
 * `previous_ranks.get(pid) - overall_rank` exactly. */
export function diffRankMovement(
  current: { player_id: string; overall_rank: number | null }[],
  previousRanksById: Record<string, number>,
): Record<string, number> {
  const movement: Record<string, number> = {};
  for (const row of current) {
    const previous = previousRanksById[row.player_id];
    if (previous !== undefined && row.overall_rank !== null) {
      movement[row.player_id] = previous - row.overall_rank;
    }
  }
  return movement;
}

export function ranksById(rows: { player_id?: string; overall_rank?: number | null }[]): Record<string, number> {
  const ranks: Record<string, number> = {};
  for (const row of rows) {
    if (row.player_id && row.overall_rank != null) {
      ranks[row.player_id] = row.overall_rank;
    }
  }
  return ranks;
}

export function diffTeamRankMovement(
  current: LiveDraftTeamRow[],
  previousRanksByRosterId: Record<string, number>,
): Record<string, number> {
  const movement: Record<string, number> = {};
  for (const row of current) {
    const key = String(row.roster_id);
    const previous = previousRanksByRosterId[key];
    if (previous !== undefined) {
      movement[key] = previous - row.team_rank;
    }
  }
  return movement;
}

export function teamRanksById(rows: LiveDraftTeamRow[]): Record<string, number> {
  const ranks: Record<string, number> = {};
  for (const row of rows) {
    ranks[String(row.roster_id)] = row.team_rank;
  }
  return ranks;
}

export function movementGlyph(movement: number | undefined): string {
  if (movement === undefined) return "—";
  if (movement >= 2) return `▲ ${movement}`;
  if (movement <= -2) return `▼ ${Math.abs(movement)}`;
  return "—";
}

export function formatLiveDraftScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "0.0";
  return value.toFixed(1);
}

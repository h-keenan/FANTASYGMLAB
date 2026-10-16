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

import type { LiveDraftPickRow, LiveDraftRankingRow, LiveDraftTeamRow, LiveDraftTradeAsset, TradeAsset } from "./api";

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

/**
 * Trade Evaluator (the last deferred piece of Revision 21) — pure display
 * helpers only, same contract as the rank-movement functions above: every
 * value/score/verdict is computed server-side by GET/POST
 * .../trade-evaluator (modules/live_draft_trade_evaluator.py, wrapping the
 * same Trade Analyzer valuation primitives). Nothing here re-derives a
 * score.
 */

/** Already-drafted players for the OTHER side of a hypothetical trade come
 * straight from the pick_rows this page already polled (never a second
 * fetch) — same dedupe-by-player_id + label format
 * `_render_trade_evaluator`'s own `player_label_by_id` builds. */
export function liveDraftDraftedPlayerOptions(
  rows: LiveDraftPickRow[],
): { key: string; label: string }[] {
  const seen = new Set<string>();
  const options: { key: string; label: string }[] = [];
  for (const row of rows) {
    if (!row.player_id || seen.has(row.player_id)) continue;
    seen.add(row.player_id);
    options.push({
      key: row.player_id,
      label: `${row.player_name || "Unknown Player"} (${row.position || "UNK"} · ${row.fantasy_team || "Unknown team"})`,
    });
  }
  return options;
}

/** Adapts a POST .../trade-evaluator asset onto the app's existing
 * `TradeAsset` shape so TradeAssetRow/ExchangeSide (Trade Analyzer,
 * Revision 15) render it with no new markup — null -> undefined is the
 * only real transform, since the server already names every field to
 * match. */
export function liveDraftAssetToTradeAsset(asset: LiveDraftTradeAsset): TradeAsset {
  return {
    asset_type: asset.asset_type,
    player_id: asset.player_id ?? undefined,
    name: asset.name ?? undefined,
    label: asset.label ?? undefined,
    position: asset.position ?? undefined,
    team: asset.team ?? undefined,
    age: asset.age,
    score: asset.score,
    injury_status: asset.injury_status ?? undefined,
    tier: asset.tier ?? undefined,
    season: asset.season ?? undefined,
    round: asset.round ?? undefined,
    owner_team_name: asset.owner_team_name ?? undefined,
  };
}

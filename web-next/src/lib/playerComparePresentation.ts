import type { QuickViewModel, RankedPlayer, WeeklyStatPoint } from "./api";
import { formatRank, formatScore } from "./leagueRankingsPresentation";

/**
 * Player Compare (Revision 12) presentation helpers — pure port of
 * modules/player_compare.py's row-building/highlight logic (itself a port of
 * mobile's lib/playerCompare.ts), extended to the exact row set the CURRENT,
 * already-layout-fixed app.py route renders (PR #1064): Value & Rank (Value
 * Score/Overall Rank/Position Rank/Age), Model Breakdown (Market/
 * Opportunity/Scarcity/Role/Age/Confidence), and Trends (Role Trend/Usage
 * Trend). No valuation/ranking/model math lives here — every number this
 * module reads is already computed server-side (GET .../rankings for the
 * Value & Rank group, GET .../quick-view's `model` for everything else);
 * this file only decides formatting, win-highlighting, and which rows are
 * worth rendering at all.
 *
 * Deliberately NOT ported: the Decision Fit narrative's win/lose framing —
 * it has none (see buildNarrativePair).
 *
 * The "Points By Week" dual chart (app.py's weekly_points_chart.py section,
 * Revision 14) IS now ported — see buildWeeklyPointsSummary below and
 * WeeklyPointsChart.tsx for the rendering half. It renders as two
 * independent single-player panels side by side (recharts), matching
 * app.py's own treatment exactly: Player Compare there calls
 * `_render_pqv_weekly_points` twice, once per column, rather than overlaying
 * both players on one chart — there is no established "Player A color" vs.
 * "Player B color" convention anywhere else on this page (ValuePill only
 * ever colors the *winning* side green), so two single-color panels is the
 * faithful port, not an invented two-series palette.
 */

export interface CompareRow {
  label: string;
  a: number | null;
  b: number | null;
  format: (value: number) => string;
  /** Only Overall Rank/Position Rank are lower-is-better, matching
   * modules/player_compare.py's CompareRow.lower_is_better and mobile's
   * LOWER_IS_BETTER set. */
  lowerIsBetter?: boolean;
}

export interface CompareTextRow {
  label: string;
  a: string | null;
  b: string | null;
}

/** Which side (if either) "wins" a numeric row — null/missing values and
 * exact ties never win, byte-for-byte port of player_compare.compare_row_html's
 * a_wins/b_wins and mobile's compareRowWinner. */
export function compareRowWinner(row: CompareRow): "a" | "b" | null {
  if (row.a === null || row.b === null || row.a === row.b) return null;
  const aWins = row.lowerIsBetter ? row.a < row.b : row.a > row.b;
  return aWins ? "a" : "b";
}

/** Matches player_compare._format_plain (Market/Opportunity/Scarcity/Role/
 * Age/the age subscore — ``Math.round(v).toString()`` in mobile terms). */
function formatPlain(value: number): string {
  return String(Math.round(value));
}

/** Matches player_compare._format_percent (Confidence). */
function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

/** Value Score / Overall Rank / Position Rank / Age — the same "how do
 * these two rank" group player_compare.build_value_rows leads with, read
 * straight off the two RankedPlayer rows GET .../rankings already returns
 * (no quick-view fetch needed for this group — score/overall_rank/
 * position_rank/age are already on that same ranked row, exactly like
 * mobile's CompareSide.player). */
export function buildValueRows(a: RankedPlayer, b: RankedPlayer): CompareRow[] {
  return [
    { label: "Value Score", a: a.score, b: b.score, format: formatScore },
    {
      label: "Overall Rank",
      a: a.overall_rank,
      b: b.overall_rank,
      format: (v) => formatRank(v),
      lowerIsBetter: true,
    },
    {
      label: "Position Rank",
      a: a.position_rank,
      b: b.position_rank,
      format: (v) => formatRank(v),
      lowerIsBetter: true,
    },
    { label: "Age", a: a.age, b: b.age, format: formatPlain },
  ];
}

/** Market / Opportunity / Scarcity / Role / Age / Confidence — the same six
 * composite-model fields player_compare.build_model_rows places head-to-head,
 * sourced from GET .../quick-view's `model` for each side (never recomputed
 * here). The age row's label follows whichever side actually has a value —
 * same `_combined_age_label` rule player_compare.py uses — since it reflects
 * a dataset-wide column choice (native age_score vs. the age_penalty
 * fallback), never a per-player one. */
export function buildModelRows(a: QuickViewModel | null, b: QuickViewModel | null): CompareRow[] {
  const ageLabel = (a?.age_score != null ? a?.age_score_label : null) ?? (b?.age_score != null ? b?.age_score_label : null) ?? "Age Score";
  return [
    { label: "Market", a: a?.market_score ?? null, b: b?.market_score ?? null, format: formatPlain },
    { label: "Opportunity", a: a?.opportunity_score ?? null, b: b?.opportunity_score ?? null, format: formatPlain },
    { label: "Scarcity", a: a?.scarcity_score ?? null, b: b?.scarcity_score ?? null, format: formatPlain },
    { label: "Role", a: a?.role_score ?? null, b: b?.role_score ?? null, format: formatPlain },
    { label: ageLabel, a: a?.age_score ?? null, b: b?.age_score ?? null, format: formatPlain },
    {
      label: "Confidence",
      a: a?.opportunity_confidence ?? null,
      b: b?.opportunity_confidence ?? null,
      format: formatPercent,
    },
  ];
}

export function hasAnyValue(rows: CompareRow[]): boolean {
  return rows.some((row) => row.a !== null || row.b !== null);
}

/** Same "Unknown" placeholder-as-nothing-to-say rule as
 * player_compare._workload_trend_text. */
function workloadTrendText(model: QuickViewModel | null): string | null {
  const value = model?.workload_trend;
  if (!value) return null;
  const text = value.trim();
  if (!text || text.toLowerCase() === "unknown") return null;
  return text;
}

/** Matches player_compare._usage_trend_text's
 * ``f"{arrow} {trend_pct:+d}% ({confidence_label})"`` — trend_pct is already
 * a signed whole-number percent off the backend's recency_trend_display
 * gate, so only the "+" for a positive read needs adding here (a negative
 * read already carries its own "-"). */
function usageTrendText(model: QuickViewModel | null): string | null {
  const trend = model?.usage_trend;
  if (!trend) return null;
  const pct = Math.round(trend.trend_pct);
  return `${trend.arrow} ${pct > 0 ? "+" : ""}${pct}% (${trend.confidence_label})`;
}

/** Role Trend / Usage Trend — only included when at least one side has a
 * real read, same "omit rather than force a value" rule as every numeric
 * row above (player_compare.build_trend_rows). */
export function buildTrendRows(a: QuickViewModel | null, b: QuickViewModel | null): CompareTextRow[] {
  const rows: CompareTextRow[] = [];
  const workloadA = workloadTrendText(a);
  const workloadB = workloadTrendText(b);
  if (workloadA !== null || workloadB !== null) {
    rows.push({ label: "Role Trend", a: workloadA, b: workloadB });
  }
  const usageA = usageTrendText(a);
  const usageB = usageTrendText(b);
  if (usageA !== null || usageB !== null) {
    rows.push({ label: "Usage Trend", a: usageA, b: usageB });
  }
  return rows;
}

export function hasAnyTextValue(rows: CompareTextRow[]): boolean {
  return rows.some((row) => row.a !== null || row.b !== null);
}

/** decision_fit_narrative is a full real sentence (player_compare.
 * decision_fit_pair/narrative_block_html) — prose, not a label+value pair,
 * so it never fits CompareRow/CompareTextRow's grid. Returns null (render
 * nothing) when neither side has a sentence, same as the Python route. */
export function buildNarrativePair(
  a: QuickViewModel | null,
  b: QuickViewModel | null,
): { a: string | null; b: string | null } | null {
  const narrativeA = a?.decision_fit_narrative ?? null;
  const narrativeB = b?.decision_fit_narrative ?? null;
  if (!narrativeA && !narrativeB) return null;
  return { a: narrativeA, b: narrativeB };
}

export interface WeeklyPointsSummary {
  games: number;
  average: number;
  peak: number;
  peakWeek: number;
}

/** Headline numbers for a Points By Week panel's caption — average, peak,
 * and the peak's week number. Pure port of
 * modules/weekly_points_chart.weekly_points_summary's arithmetic (a plain
 * average/max over already-scored weekly PPR totals — no scoring logic,
 * just aggregation over numbers the Python engine already computed). Drops
 * any week missing a PPR total first, same "absent, not zero" rule
 * modules/weekly_points_chart.normalize_week_points documents (an unplayed
 * week carries no fantasy_points_ppr at all, not a zero). */
export function buildWeeklyPointsSummary(weeks: WeeklyStatPoint[]): WeeklyPointsSummary {
  const played = weeks.filter((week): week is WeeklyStatPoint & { fantasy_points_ppr: number } => week.fantasy_points_ppr != null);
  if (played.length === 0) {
    return { games: 0, average: 0, peak: 0, peakWeek: 0 };
  }
  const total = played.reduce((sum, week) => sum + week.fantasy_points_ppr, 0);
  const peakWeek = played.reduce((best, week) => (week.fantasy_points_ppr > best.fantasy_points_ppr ? week : best), played[0]);
  return {
    games: played.length,
    average: total / played.length,
    peak: peakWeek.fantasy_points_ppr,
    peakWeek: peakWeek.week,
  };
}

/** Opponent-picker default suggestion ordering — mirrors
 * PlayerCompareScreen.tsx's defaultSuggestions: same position as the base
 * player when known, sorted by proximity to the base player's own score (so
 * the list reads "around" the base player's level, not top-down by raw
 * score), capped the same way mobile caps its own list. */
export function defaultCompareCandidates(
  pool: RankedPlayer[],
  basePlayer: RankedPlayer,
  limit = 50,
): RankedPlayer[] {
  const scoped = basePlayer.position ? pool.filter((p) => p.position === basePlayer.position) : pool;
  const baseScore = basePlayer.score;
  if (baseScore == null) return scoped.slice(0, limit);
  return [...scoped]
    .sort((x, y) => {
      const dx = x.score == null ? Infinity : Math.abs(x.score - baseScore);
      const dy = y.score == null ? Infinity : Math.abs(y.score - baseScore);
      return dx - dy;
    })
    .slice(0, limit);
}

/** Once the user actually types a name, search the FULL pool by name match
 * (unrestricted by position/score window) — only the default, pre-search
 * suggestion list above is scoped to the base player's own level, matching
 * mobile's filteredCandidates. */
export function searchCompareCandidates(pool: RankedPlayer[], query: string, limit = 50): RankedPlayer[] {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return [];
  return pool.filter((p) => (p.name ?? "").toLowerCase().includes(trimmed)).slice(0, limit);
}

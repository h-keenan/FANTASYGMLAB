import type { QuickViewModel, RankedPlayer, UsageTrend } from './api';

/** One side of a head-to-head comparison — the same real /quick-view fetch
 * Player Detail (PQV) already makes for a single player, just held for two
 * players at once. Never a second/duplicate computation of anything Player
 * Detail already computes server-side. */
export interface CompareSide {
  player: RankedPlayer;
  overallRating: number | null;
  model: QuickViewModel | null;
}

/** One head-to-head row for a NUMERIC field: label, both sides' real
 * values, and which side (if either) reads higher. Never a synthesized
 * "winner" score — just highlights whichever real number is bigger, or
 * neither when they tie or either side is missing. */
export interface CompareRow {
  label: string;
  a: number | null;
  b: number | null;
  format?: (value: number) => string;
}

/** One head-to-head row for a CATEGORICAL/text field (e.g. Status, Injury
 * Status, Role trend direction) that doesn't reduce to a single comparable
 * number — rendered as a plain side-by-side pair with no "winner" pill. */
export interface CompareTextRow {
  label: string;
  a: string | null;
  b: string | null;
}

/** Rows where a LOWER number is the better outcome (ranks) — everything
 * else (Value Score, model subscores, age, trend %, confidence) defaults to
 * higher-is-better. */
export const LOWER_IS_BETTER = new Set(['Overall Rank', 'Position Rank']);

/** Which side (if either) "wins" a numeric compare row — null/missing values
 * and exact ties never win. Shared by the on-screen CompareRowView and the
 * shareable CompareShareCard (mobile/src/components/CompareShareCard.tsx)
 * so the win-highlight logic is computed once instead of two copies of the
 * same tie/lower-is-better check living in two files. */
export function compareRowWinner(row: CompareRow): 'a' | 'b' | null {
  if (row.a === null || row.b === null || row.a === row.b) return null;
  const lowerIsBetter = LOWER_IS_BETTER.has(row.label);
  const aWins = lowerIsBetter ? row.a < row.b : row.a > row.b;
  return aWins ? 'a' : 'b';
}

// Value Score / Overall Rank / Position Rank / Age — the same "how do these
// two rank" context PlayerSnapshotCard leads with on Player Detail, just
// doubled for a head-to-head read instead of one player's own snapshot.
// Overall Rank + Position Rank both come straight off the same RankedPlayer
// object Player Detail's Snapshot card renders (see PlayerDetailScreen's
// `rank` state) — no new field, just added to the head-to-head instead of
// only ever appearing on Player Detail.
export function buildValueRows(a: CompareSide, b: CompareSide): CompareRow[] {
  return [
    {
      label: 'Value Score',
      a: a.player.score,
      b: b.player.score,
      format: (v) => Math.round(v).toLocaleString(),
    },
    {
      label: 'Overall Rank',
      a: a.player.overall_rank,
      b: b.player.overall_rank,
      format: (v) => `#${v}`,
    },
    {
      label: 'Position Rank',
      a: a.player.position_rank,
      b: b.player.position_rank,
      format: (v) => `#${v}`,
    },
    { label: 'Age', a: a.player.age, b: b.player.age },
  ];
}

/** Same five composite subscores PlayerDetailScreen's ModelSection already
 * renders (market/opportunity/scarcity/role/age) plus the model's own
 * opportunity_confidence — never recomputed here, just placed head-to-head
 * instead of alongside one player's own breakdown. The age row's label
 * follows whichever side actually has a model (native "Age Score" vs. the
 * "Age Lens" fallback — see QuickViewModel.age_score_label's docstring);
 * both sides always share the same label since it reflects a dataset-wide
 * column choice, not a per-player one. */
export function buildModelRows(a: CompareSide, b: CompareSide): CompareRow[] {
  const ageLabel = a.model?.age_score_label ?? b.model?.age_score_label ?? 'Age Score';
  return [
    {
      label: 'Market',
      a: a.model?.market_score ?? null,
      b: b.model?.market_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: 'Opportunity',
      a: a.model?.opportunity_score ?? null,
      b: b.model?.opportunity_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: 'Scarcity',
      a: a.model?.scarcity_score ?? null,
      b: b.model?.scarcity_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: 'Role',
      a: a.model?.role_score ?? null,
      b: b.model?.role_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: ageLabel,
      a: a.model?.age_score ?? null,
      b: b.model?.age_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: 'Confidence',
      a: a.model?.opportunity_confidence ?? null,
      b: b.model?.opportunity_confidence ?? null,
      format: (v) => `${Math.round(v)}%`,
    },
  ];
}

/** usage_trend.trend_pct is a real signed number (see UsageTrend's own
 * docstring in api.ts) — the one piece of the two trend signals PQV shows
 * that genuinely reduces to a single comparable figure, so it gets a
 * numeric row like Model Breakdown above. workload_trend (a bare direction
 * word — "rising"/"falling"/etc, see PlayerDetailScreen's InsightChipsRow)
 * has no magnitude to compare, so it's a text row instead (buildStatusRows
 * below) rather than being force-fit into a number. */
export function buildTrendRows(a: CompareSide, b: CompareSide): CompareRow[] {
  const usageA: UsageTrend | null = a.model?.usage_trend ?? null;
  const usageB: UsageTrend | null = b.model?.usage_trend ?? null;
  return [
    {
      label: 'Usage Trend',
      a: usageA ? usageA.trend_pct : null,
      b: usageB ? usageB.trend_pct : null,
      format: (v) => `${v > 0 ? '+' : ''}${Math.round(v)}%`,
    },
  ];
}

/** Categorical fields with no shared numeric scale — Status/Injury Status
 * (same real strings every list screen already shows, see RankedPlayer) and
 * Role trend direction (model.workload_trend, a bare word like "rising" —
 * see PlayerDetailScreen's InsightChipsRow). Rendered as plain side-by-side
 * pairs with no synthesized "winner", since there's no real number here to
 * compare. Empty strings are treated the same as null/undefined — the API
 * already uses '' for "known no trend"-style non-answers in a few places
 * (see RankedPlayer.usage_trend's optionality note), and an empty text row
 * would just render as a blank pair either way. */
export function buildStatusRows(a: CompareSide, b: CompareSide): CompareTextRow[] {
  const rows: CompareTextRow[] = [
    { label: 'Status', a: a.player.status || null, b: b.player.status || null },
    { label: 'Injury Status', a: a.player.injury_status || null, b: b.player.injury_status || null },
  ];
  const workloadA = a.model?.workload_trend || null;
  const workloadB = b.model?.workload_trend || null;
  if (workloadA || workloadB) {
    rows.push({ label: 'Role Trend', a: workloadA, b: workloadB });
  }
  return rows;
}

/** decision_fit_narrative is a full sentence (see QuickViewModel's
 * docstring) — prose, not a number, so it can never be a CompareRow. This
 * just pairs the two real sentences for a side-by-side text block; returns
 * null when neither side has one so the caller can skip the whole section
 * rather than rendering two empty text blocks. */
export function buildNarrativePair(a: CompareSide, b: CompareSide): { a: string | null; b: string | null } | null {
  const narrativeA = a.model?.decision_fit_narrative ?? null;
  const narrativeB = b.model?.decision_fit_narrative ?? null;
  if (!narrativeA && !narrativeB) return null;
  return { a: narrativeA, b: narrativeB };
}

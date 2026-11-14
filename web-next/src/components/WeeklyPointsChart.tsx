"use client";

import { TrendChart } from "@/components/ui/TrendChart";
import type { WeeklyStatPoint } from "@/lib/api";
import { weeklyGapRows, type ChartBandPoint, type ChartInputPoint } from "@/lib/chartSeries";
import type { WeeklyProjectionPoint } from "@/lib/weeklyProjection";
import { CHART_HEIGHT } from "@/components/weeklyPointsChartHeight";

/**
 * Points By Week: the weekly points (or any per-step number) chart. A thin adapter over the ONE shared
 * trend chart (components/ui/TrendChart.tsx, data rules in lib/chartSeries.ts): it only turns weekly rows
 * into chart points. Missed / bye weeks inside the played range become gaps (dashed bridge + muted marker,
 * never a blank hole); a single played week renders as a labelled stat; two or three weeks get the sparse
 * layout. Mobile twin: mobile/src/components/WeeklyPointsChart.tsx.
 *
 * Deliberately independent single-series panels (Player Compare renders two side by side), not one chart
 * with two overlaid lines: see playerComparePresentation.ts.
 */
export { CHART_HEIGHT };

/** Rows for the shared chart: every week from the first to the last played one, gaps explicit. */
export function weeklyChartPoints(weeks: readonly WeeklyStatPoint[], byeWeeks: readonly number[] = [], xLabel = "Wk"): ChartInputPoint[] {
  return weeklyGapRows(weeks.map((w) => ({ week: w.week, points: w.fantasy_points_ppr })), byeWeeks, xLabel);
}

export function WeeklyPointsPanel({
  name,
  weeks,
  season,
  projection = null,
  pointsLabel = "PPR points",
  emptyText,
  xLabel = "Week",
  byeWeeks = [],
}: {
  name: string;
  weeks: WeeklyStatPoint[];
  season: number;
  /** Optional rest-of-season projection drawn as a band behind / after the played weeks (Fantasy Sim). Omit for a plain history chart. */
  projection?: readonly WeeklyProjectionPoint[] | null;
  /** Unit in the tooltip and summary ("PPR points" by default). */
  pointsLabel?: string;
  /** Replaces the "no weekly fantasy points" line when nothing is played and there is no projection. */
  emptyText?: string;
  /** What the x axis counts ("Week" by default; the development curve plots "Year"). */
  xLabel?: string;
  /** Weeks the player's team is off: a played-range hole on one of these is labelled "Bye week", not "No game". */
  byeWeeks?: readonly number[];
  /** Kept for call-site compatibility; the shared chart ids its own gradient. */
  gradientId?: string;
}) {
  const band: ChartBandPoint[] | null = projection && projection.length > 0 ? projection.map((p) => ({ x: p.week, mean: p.mean, floor: p.floor, ceiling: p.ceiling })) : null;
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div
        className="uppercase font-bold truncate"
        style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {name}
      </div>
      <TrendChart
        points={weeklyChartPoints(weeks, byeWeeks, xLabel === "Week" ? "Wk" : xLabel)}
        band={band}
        name={name}
        unit={pointsLabel}
        xNoun={xLabel.toLowerCase()}
        formatX={(x) => String(x)}
        includeZero
        height={CHART_HEIGHT}
        emptyText={emptyText ?? `No weekly fantasy points are recorded for the ${season} season yet.`}
        testId="weekly-points-chart"
      />
    </div>
  );
}

export function WeeklyPointsChart({
  playerAName,
  playerBName,
  weeksA,
  weeksB,
  season,
}: {
  playerAName: string;
  playerBName: string;
  weeksA: WeeklyStatPoint[];
  weeksB: WeeklyStatPoint[];
  season: number;
}) {
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3">
      <WeeklyPointsPanel name={playerAName || "Player A"} weeks={weeksA} season={season} />
      <WeeklyPointsPanel name={playerBName || "Player B"} weeks={weeksB} season={season} />
    </div>
  );
}

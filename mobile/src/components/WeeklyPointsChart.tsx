import React from 'react';

import type { WeeklyStatPoint } from '../lib/api';
import { weeklyGapRows, type ChartBandPoint, type ChartInputPoint, type WeeklyGapOptions } from '../lib/chartSeries';
import type { WeeklyProjectionPoint } from '../lib/weeklyProjection';
import TrendChart from './TrendChart';

/** Every week from the first to the last played one, gaps explicit (shared with the web twin's weeklyChartPoints). */
export function weeklyChartPoints(weeks: readonly WeeklyStatPoint[], byeWeeks: readonly number[] = [], xLabel = 'Wk', options: WeeklyGapOptions = {}): ChartInputPoint[] {
  return weeklyGapRows(weeks.map((w) => ({ week: w.week, points: w.fantasy_points_ppr })), byeWeeks, xLabel, options);
}

/** A player's fantasy points across the weeks of one season: a thin adapter over the ONE shared TrendChart
 * (missed / bye weeks are dashed gaps, one played week is a labelled stat, projection band optional).
 * Web twin: web-next/src/components/WeeklyPointsChart.tsx. */
export default function WeeklyPointsChart({
  weeks,
  projection = null,
  pointsLabel = 'pts',
  emptyText,
  xLabel = 'Week',
  byeWeeks = [],
  inactiveWeeks = [],
  injuredWeeks = [],
  throughWeek = null,
}: {
  weeks: WeeklyStatPoint[];
  /** Optional rest-of-season projection drawn as a band (Fantasy Sim). */
  projection?: readonly WeeklyProjectionPoint[] | null;
  pointsLabel?: string;
  emptyText?: string;
  /** What the x axis counts (the development curve plots 'Year'). */
  xLabel?: string;
  /** Weeks the team is off: a hole on one of these reads "Bye week", not "No game". */
  byeWeeks?: readonly number[];
  /** Weeks the provider confirms he did not play (his team did). */
  inactiveWeeks?: readonly number[];
  /** Weeks he was out injured (a dashed, labelled gap, like inactive). */
  injuredWeeks?: readonly number[];
  /** Current NFL week: the axis runs to here; completed weeks with no data show a 'no data' break. */
  throughWeek?: number | null;
}) {
  const band: ChartBandPoint[] | null = projection && projection.length > 0 ? projection.map((p) => ({ x: p.week, mean: p.mean, floor: p.floor, ceiling: p.ceiling })) : null;
  return (
    <TrendChart
      points={weeklyChartPoints(weeks, byeWeeks, xLabel === 'Week' ? 'Wk' : xLabel, { inactiveWeeks, injuredWeeks, throughWeek })}
      xMax={throughWeek}
      band={band}
      name="Points by week"
      unit={pointsLabel}
      xNoun={xLabel.toLowerCase()}
      includeZero
      height={140}
      emptyText={emptyText ?? 'No weekly points recorded for this season yet.'}
      testID="weekly-points-chart"
    />
  );
}

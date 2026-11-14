import React from 'react';

import type { RatingHistoryPoint } from '../lib/api';
import type { ChartInputPoint } from '../lib/chartSeries';
import { shortDate } from '../lib/valueHistoryPresentation';
import TrendChart from './TrendChart';

const DAY_MS = 86_400_000;
const dayOf = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? Math.round(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / DAY_MS) : NaN;
};

/** Stored snapshots on a real day axis: a quiet stretch is a long segment, not extra points. */
export function ratingChartPoints(points: readonly RatingHistoryPoint[]): ChartInputPoint[] {
  return points.map((p) => ({ x: dayOf(p.date), y: p.rating, label: shortDate(p.date) })).filter((p) => Number.isFinite(p.x));
}

/** Overall rating (0-99) over the real stored daily snapshots, drawn by the shared TrendChart. Tap a point for its date and value.
 * Web twin: web-next/src/components/RatingHistoryChart.tsx. */
export default function RatingHistoryChart({ points }: { points: RatingHistoryPoint[] }) {
  return (
    <TrendChart
      points={ratingChartPoints(points)}
      name="Overall rating"
      unit="rating"
      xNoun="day"
      formatX={(day) => shortDate(new Date(day * DAY_MS).toISOString())}
      formatY={(v) => String(Math.round(v))}
      yPad={3}
      clamp={[0, 99]}
      height={140}
      testID="rating-history-chart"
    />
  );
}

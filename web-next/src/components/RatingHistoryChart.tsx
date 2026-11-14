"use client";

import { TrendChart } from "@/components/ui/TrendChart";
import type { RatingHistoryPoint } from "@/lib/api";
import type { ChartInputPoint } from "@/lib/chartSeries";
import { shortDate } from "@/lib/valueHistoryPresentation";

/** Overall rating (0-99) over the real stored daily snapshots, drawn by the shared TrendChart (tokens only). */
export const RATING_CHART_HEIGHT = 140;

const DAY_MS = 86_400_000;
const dayOf = (iso: string) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? Math.round(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / DAY_MS) : NaN;
};

/** Stored snapshots on a real day axis: a quiet stretch is a long line segment, not extra points. */
export function ratingChartPoints(points: readonly RatingHistoryPoint[]): ChartInputPoint[] {
  return points.map((p) => ({ x: dayOf(p.date), y: p.rating, label: shortDate(p.date) })).filter((p) => Number.isFinite(p.x));
}

export function RatingHistoryChart({ points }: { points: RatingHistoryPoint[]; gradientId?: string }) {
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
      height={RATING_CHART_HEIGHT}
      testId="rating-history-chart"
    />
  );
}

"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { RatingHistoryPoint } from "@/lib/api";
import { shortDate } from "@/lib/valueHistoryPresentation";

/** Overall rating (0-99) over the real stored daily snapshots. Same recharts
 * styling as WeeklyPointsChart (tokens only); lazy-loaded via
 * RatingHistoryChartLazy so recharts stays out of the main PQV bundle. */
export const RATING_CHART_HEIGHT = 140;

export function RatingHistoryChart({ points, gradientId }: { points: RatingHistoryPoint[]; gradientId: string }) {
  const values = points.map((p) => p.rating);
  const lo = Math.max(0, Math.min(...values) - 3);
  const hi = Math.min(99, Math.max(...values) + 3);
  return (
    <div style={{ width: "100%", height: RATING_CHART_HEIGHT }} aria-hidden="true" data-testid="rating-history-chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--color-border)" strokeOpacity={0.6} />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }}
            tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
            tickFormatter={shortDate}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            domain={[lo, hi]}
            tickLine={false}
            axisLine={false}
            width={28}
            tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
            allowDecimals={false}
          />
          <Tooltip
            formatter={(value) => [`${value}`, "Rating"]}
            labelFormatter={(label) => shortDate(String(label))}
            contentStyle={{
              background: "var(--color-surface-secondary)",
              border: "var(--border-width-default) solid var(--color-border)",
              borderRadius: "var(--radius-control)",
              color: "var(--color-text-primary)",
              fontSize: "0.75rem",
            }}
            labelStyle={{ color: "var(--color-text-muted)" }}
          />
          <Area
            type="monotone"
            dataKey="rating"
            stroke="var(--color-accent)"
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={{ r: points.length > 30 ? 0 : 3, fill: "var(--color-accent)", strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

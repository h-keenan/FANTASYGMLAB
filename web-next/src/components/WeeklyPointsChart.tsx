"use client";

import { Area, AreaChart, CartesianGrid, Dot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DotProps } from "recharts";

import type { WeeklyStatPoint } from "@/lib/api";
import { buildWeeklyPointsSummary, fillWeeklyPointGaps } from "@/lib/playerComparePresentation";
import { buildWeeklyChartRows, type WeeklyProjectionPoint } from "@/lib/weeklyProjection";

/**
 * Points By Week — web-next's port of app.py's weekly_points_chart.py
 * (`_render_pqv_weekly_points`, called twice side by side for Player
 * Compare) and mobile's WeeklyPointsChart.tsx. First chart in web-next, so
 * this also establishes the pattern (recharts — see the PR description for
 * why) future charts should follow: a `recharts` primitive wrapped in a
 * thin presentational component, reading only design tokens already
 * defined in globals.css, with the real math (buildWeeklyPointsSummary)
 * living in playerComparePresentation.ts so it stays unit-testable without
 * mounting any SVG.
 *
 * Deliberately two independent single-series panels, not one chart with
 * two overlaid lines — see playerComparePresentation.ts's module docstring
 * for why that's the faithful port rather than an invented two-color
 * convention.
 */

// Exported so PlayerTrendsPanel.tsx's loading skeleton can reserve this
// exact footprint instead of a second, independently-guessed number that
// could drift from this one and reintroduce a layout jump when the real
// chart swaps in.
import { CHART_HEIGHT } from "@/components/weeklyPointsChartHeight";

export { CHART_HEIGHT };

function formatPoints(value: number): string {
  return value.toFixed(1);
}

function PeakDot(props: DotProps & { peakWeek: number }) {
  const { cx, cy, payload, peakWeek } = props as DotProps & {
    peakWeek: number;
    payload?: { week: number; fantasy_points_ppr: number | null };
  };
  // A gap week (null points, inserted by fillWeeklyPointGaps) has no real
  // position to dot — recharts still invokes this renderer for it since the
  // numeric x-axis still has an x coordinate for every week in range.
  if (cx == null || cy == null || Number.isNaN(cy) || !payload || payload.fantasy_points_ppr == null) return null;
  const isPeak = payload.week === peakWeek;
  return (
    <Dot
      cx={cx}
      cy={cy}
      r={isPeak ? 4.5 : 3}
      fill={isPeak ? "var(--color-accent-strong)" : "var(--color-accent)"}
      stroke="var(--color-surface-secondary)"
      strokeWidth={1}
    />
  );
}

function WeeklyPointsEmpty({ season, text }: { season: number; text?: string }) {
  return (
    <p className="text-xs px-1 py-6 text-center" style={{ color: "var(--color-text-muted)" }}>
      {text ?? `No weekly fantasy points are recorded for the ${season} season yet.`}
    </p>
  );
}

export function WeeklyPointsPanel({
  name,
  weeks,
  season,
  gradientId,
  projection = null,
  pointsLabel = "PPR points",
  emptyText,
  xLabel = "Week",
}: {
  name: string;
  weeks: WeeklyStatPoint[];
  season: number;
  /** Optional rest-of-season projection drawn as a band behind the played weeks (Fantasy Sim). Omit for a plain history chart. */
  projection?: readonly WeeklyProjectionPoint[] | null;
  /** Unit in the tooltip and summary ("PPR points" by default). */
  pointsLabel?: string;
  /** Replaces the "no weekly fantasy points" line when nothing is played and there is no projection. */
  emptyText?: string;
  /** What the x axis counts ("Week" by default; the development curve plots "Year"). */
  xLabel?: string;
  /** Unique per panel — two <defs><linearGradient> on the same page with the
   * same id would collide (the second panel would silently paint with the
   * first panel's gradient), same reason app.py's own _gradient_id scopes
   * by player+season. */
  gradientId: string;
}) {
  const hasPlayedWeek = weeks.some((week) => week.fantasy_points_ppr != null);

  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div
        className="uppercase font-bold truncate"
        style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-badge)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {name}
      </div>
      {!hasPlayedWeek && !(projection && projection.length > 0) ? (
        <WeeklyPointsEmpty season={season} text={emptyText} />
      ) : (
        <PlayedWeeksChart weeks={weeks} gradientId={gradientId} name={name} projection={projection} pointsLabel={pointsLabel} xLabel={xLabel} />
      )}
    </div>
  );
}

function PlayedWeeksChart({
  weeks,
  gradientId,
  name,
  projection,
  pointsLabel,
  xLabel,
}: {
  xLabel: string;
  weeks: WeeklyStatPoint[];
  gradientId: string;
  name: string;
  projection: readonly WeeklyProjectionPoint[] | null;
  pointsLabel: string;
}) {
  const dense = fillWeeklyPointGaps(weeks);
  const hasProjection = Boolean(projection && projection.length > 0);
  // With a projection the rows also carry the rest-of-season band; without one this is exactly the plain history chart.
  const rows: Array<WeeklyStatPoint & { proj_mean?: number | null; proj_band?: [number, number] | null }> = hasProjection
    ? buildWeeklyChartRows(
        dense.map((w) => ({ week: w.week, points: w.fantasy_points_ppr })),
        projection,
      ).map((r) => ({
        week: r.week,
        fantasy_points_ppr: r.actual,
        snap_share: null,
        proj_mean: r.mean,
        proj_band: r.floor != null && r.ceiling != null ? ([r.floor, r.ceiling] as [number, number]) : null,
      }))
    : dense;
  const summary = buildWeeklyPointsSummary(dense);
  const values = rows.map((row) => row.fantasy_points_ppr).filter((value): value is number => value != null);
  const ceilings = rows.map((row) => row.proj_band?.[1]).filter((value): value is number => value != null);
  const projMeans = rows.map((row) => row.proj_mean).filter((value): value is number => value != null);
  // Same framing as app.py's weekly_points_chart_html: the floor never rises
  // above zero and the ceiling never drops below 1, so a quiet season still
  // reads as a legible shape instead of amplifying noise.
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(1, ...values, ...ceilings);
  const firstWeek = rows[0].week;
  const lastWeek = rows[rows.length - 1].week;
  const projAverage = projMeans.length > 0 ? projMeans.reduce((a, b) => a + b, 0) / projMeans.length : null;

  const accessibleSummary =
    `Points by week for ${name}: ${summary.games} game${summary.games !== 1 ? "s" : ""}, ` +
    `average ${formatPoints(summary.average)} ${pointsLabel}, high ${formatPoints(summary.peak)} in week ${summary.peakWeek}.` +
    (projAverage != null ? ` Projected ${formatPoints(projAverage)} per game for the weeks ahead.` : "");

  return (
    <div className="flex flex-col gap-1">
      {/* The SVG below is decorative to assistive tech (recharts doesn't
          expose a data table), so the real content — same numbers the
          caption already prints visually — is this one sr-only sentence,
          matching app.py's own `aria-label` on its inline-SVG version of
          this chart. */}
      <p className="sr-only">{accessibleSummary}</p>
      <div style={{ width: "100%", height: CHART_HEIGHT }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="0" strokeOpacity={0.6} />
            <XAxis
              dataKey="week"
              type="number"
              domain={[firstWeek, lastWeek]}
              allowDecimals={false}
              tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }}
              tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
              interval={rows.length > 10 ? 1 : 0}
            />
            <YAxis
              domain={[minimum, maximum]}
              tickLine={false}
              axisLine={false}
              width={22}
              tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
              tickFormatter={(value: number) => value.toFixed(0)}
            />
            <Tooltip
              formatter={(value, key) =>
                key === "proj_band" && Array.isArray(value)
                  ? [`${formatPoints(Number(value[0]))}-${formatPoints(Number(value[1]))} projected`, undefined]
                  : key === "proj_mean"
                    ? [`${formatPoints(Number(value))} projected`, undefined]
                    : [`${formatPoints(Number(value))} ${pointsLabel}`, undefined]
              }
              labelFormatter={(label) => `${xLabel} ${label}`}
              contentStyle={{
                background: "var(--color-surface-secondary)",
                border: "var(--border-width-default) solid var(--color-border)",
                borderRadius: "var(--radius-control)",
                color: "var(--color-text-primary)",
                fontSize: "0.75rem",
              }}
              labelStyle={{ color: "var(--color-text-muted)" }}
            />
            {hasProjection ? (
              <>
                <Area type="monotone" dataKey="proj_band" stroke="none" fill="var(--color-accent)" fillOpacity={0.16} isAnimationActive={false} connectNulls={false} />
                <Area type="monotone" dataKey="proj_mean" stroke="var(--color-accent)" strokeOpacity={0.7} strokeDasharray="4 3" strokeWidth={1.5} fill="none" dot={false} isAnimationActive={false} connectNulls={false} />
              </>
            ) : null}
            <Area
              type="monotone"
              dataKey="fantasy_points_ppr"
              stroke="var(--color-accent)"
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              dot={<PeakDot peakWeek={summary.peakWeek} />}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {summary.games > 0 ? (
        <p className="text-xs text-center" style={{ color: "var(--color-text-secondary)" }}>
          <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(summary.average)}</strong> avg &middot;{" "}
          <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(summary.peak)}</strong> high (Wk {summary.peakWeek}) &middot;{" "}
          <strong style={{ color: "var(--color-text-primary)" }}>{summary.games}</strong> week{summary.games !== 1 ? "s" : ""} played
          {projAverage != null ? (
            <>
              {" "}&middot; <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(projAverage)}</strong> projected
            </>
          ) : null}
        </p>
      ) : projAverage != null ? (
        <p className="text-xs text-center" style={{ color: "var(--color-text-secondary)" }}>
          <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(projAverage)}</strong> projected per game
        </p>
      ) : null}
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
      <WeeklyPointsPanel name={playerAName || "Player A"} weeks={weeksA} season={season} gradientId="wpc-fill-a" />
      <WeeklyPointsPanel name={playerBName || "Player B"} weeks={weeksB} season={season} gradientId="wpc-fill-b" />
    </div>
  );
}

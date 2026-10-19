"use client";

import { Area, AreaChart, CartesianGrid, Dot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DotProps } from "recharts";

import type { WeeklyStatPoint } from "@/lib/api";
import { buildWeeklyPointsSummary, fillWeeklyPointGaps } from "@/lib/playerComparePresentation";

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

const CHART_HEIGHT = 160;

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

function WeeklyPointsEmpty({ season }: { season: number }) {
  return (
    <p className="text-xs px-1 py-6 text-center" style={{ color: "var(--color-text-muted)" }}>
      No weekly fantasy points are recorded for the {season} season yet.
    </p>
  );
}

export function WeeklyPointsPanel({
  name,
  weeks,
  season,
  gradientId,
}: {
  name: string;
  weeks: WeeklyStatPoint[];
  season: number;
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
      {!hasPlayedWeek ? (
        <WeeklyPointsEmpty season={season} />
      ) : (
        <PlayedWeeksChart weeks={fillWeeklyPointGaps(weeks)} gradientId={gradientId} name={name} />
      )}
    </div>
  );
}

function PlayedWeeksChart({ weeks, gradientId, name }: { weeks: WeeklyStatPoint[]; gradientId: string; name: string }) {
  const summary = buildWeeklyPointsSummary(weeks);
  const values = weeks
    .map((week) => week.fantasy_points_ppr)
    .filter((value): value is number => value != null);
  // Same framing as app.py's weekly_points_chart_html: the floor never rises
  // above zero and the ceiling never drops below 1, so a quiet season still
  // reads as a legible shape instead of amplifying noise.
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(1, ...values);
  const firstWeek = weeks[0].week;
  const lastWeek = weeks[weeks.length - 1].week;

  const accessibleSummary =
    `Points by week for ${name}: ${summary.games} game${summary.games !== 1 ? "s" : ""}, ` +
    `average ${formatPoints(summary.average)} PPR points, high ${formatPoints(summary.peak)} in week ${summary.peakWeek}.`;

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
          <AreaChart data={weeks} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
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
              interval={weeks.length > 10 ? 1 : 0}
            />
            <YAxis
              domain={[minimum, maximum]}
              tickLine={false}
              axisLine={false}
              width={28}
              tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
              tickFormatter={(value: number) => value.toFixed(0)}
            />
            <Tooltip
              formatter={(value) => [`${formatPoints(Number(value))} PPR points`, undefined]}
              labelFormatter={(label) => `Week ${label}`}
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
      <p className="text-xs text-center" style={{ color: "var(--color-text-secondary)" }}>
        <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(summary.average)}</strong> avg &middot;{" "}
        <strong style={{ color: "var(--color-text-primary)" }}>{formatPoints(summary.peak)}</strong> high (Wk {summary.peakWeek}) &middot;{" "}
        <strong style={{ color: "var(--color-text-primary)" }}>{summary.games}</strong> week{summary.games !== 1 ? "s" : ""} played
      </p>
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

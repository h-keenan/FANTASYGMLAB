"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  areaPath,
  bandPathFor,
  chartPlaceholder,
  chartSummary,
  formatTick,
  GAP_LABEL,
  gapCaption,
  linePath,
  makeScales,
  prepareSeries,
  singleBarFraction,
  type ChartBandPoint,
  type ChartInputPoint,
  type ChartPad,
  type ChartPoint,
  type PrepareOptions,
} from "@/lib/chartSeries";

import "./ui.css";

/**
 * THE trend chart: every line / area chart in the web app goes through this one component (weekly points,
 * rating history, rank journey, the Fantasy Sim projection band). The data rules live in lib/chartSeries.ts
 * (mobile twin: mobile/src/components/TrendChart.tsx on the identical lib), so a chart can never disagree
 * with the app about what a gap or a lone point looks like:
 *   - bye / missed / injured weeks break the line: a dashed bridge and a muted hollow marker, never a hole;
 *   - one played point renders a labelled stat with a mini bar, not a dot; nothing renders a short sentence;
 *   - two or three points get wide spacing, bigger dots and direct value labels;
 *   - tap, hover or focus a point for a tooltip (keyboard reachable); `compact` is the axis-free sparkline;
 *   - smoothing is monotone (no overshoot); the draw-in animation is off under prefers-reduced-motion.
 * Tokens only (accent, border, text, surface); no hard-coded colors.
 */
export interface TrendChartProps {
  points: readonly ChartInputPoint[];
  /** Projection band (floor / ceiling / mean) shown behind and after the played data. */
  band?: readonly ChartBandPoint[] | null;
  /** Who / what this is, for the accessible summary. */
  name: string;
  /** Unit in tooltips and the summary ("PPR points", "rating"). */
  unit?: string;
  /** What one x step is called ("week", "year", "day"). */
  xNoun?: string;
  formatX?: (x: number) => string;
  formatY?: (y: number) => string;
  variant?: "full" | "compact";
  height?: number;
  includeZero?: boolean;
  yPad?: number;
  clamp?: [number, number] | null;
  /** Exact y domain, e.g. [1, teams] for a rank. */
  yDomain?: [number, number] | null;
  yTickCount?: number;
  /** Rank-style axis: low values at the top. */
  invertY?: boolean;
  smooth?: boolean;
  /** Shown when there is nothing to draw. */
  emptyText?: string;
  /** Per-point dot color (a token), e.g. best / worst of a journey. */
  pointColor?: (point: ChartPoint, ctx: { peak: ChartPoint | null; low: ChartPoint | null }) => string | undefined;
  testId?: string;
}

const FULL_PAD: ChartPad = { top: 14, right: 10, bottom: 22, left: 30 };
const COMPACT_PAD: ChartPad = { top: 6, right: 6, bottom: 6, left: 6 };
const DEFAULT_FORMAT = (v: number) => v.toFixed(1);

function useWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    setWidth(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

export function TrendChart(props: TrendChartProps) {
  const { points, band = null, name, unit = "", xNoun = "week", formatX = (x) => String(x), formatY = DEFAULT_FORMAT, variant = "full", includeZero = false, yPad = 0, clamp = null, yDomain = null, yTickCount = 4, invertY = false, smooth = true, emptyText, pointColor, testId } = props;
  const compact = variant === "compact";
  const height = props.height ?? (compact ? 44 : 160);
  const pad = compact ? COMPACT_PAD : FULL_PAD;
  const gradientId = useId().replace(/:/g, "");
  const [ref, width] = useWidth();
  // The selection belongs to one `points` array: new data drops it (no effect needed).
  const [pick, setPick] = useState<{ points: readonly ChartInputPoint[]; key: string | null }>({ points, key: null });
  const selected = pick.points === points ? pick.key : null;
  const setSelected = (next: string | null | ((cur: string | null) => string | null)) => setPick({ points, key: typeof next === "function" ? next(selected) : next });

  const options: PrepareOptions = { includeZero, yPad, clamp, yDomain, yTickCount, band };
  const series = useMemo(() => prepareSeries(points, options), [points, band, includeZero, yPad, clamp, yDomain, yTickCount]); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = chartSummary(series, name, unit, xNoun, formatY);

  if (series.status === "empty") {
    return (
      <p className="py-4 text-center text-xs" style={{ color: "var(--color-text-muted)" }} data-testid={testId ? `${testId}-empty` : undefined}>
        {emptyText ?? chartPlaceholder("empty", `${xNoun}s`)}
      </p>
    );
  }
  if (series.status === "single" && series.played[0]) {
    const only = series.played[0];
    const [, top] = series.yDomain;
    const fraction = singleBarFraction(only.y, [Math.min(0, series.yDomain[0]), top]);
    return (
      <div className="trend-stat" data-testid={testId ? `${testId}-single` : "trend-chart-single"} role="group" aria-label={summary}>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xl font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
            {formatY(only.y)}
            {unit ? <span className="ml-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>{unit}</span> : null}
          </span>
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{only.label ?? formatX(only.x)}</span>
        </div>
        {compact ? null : (
          <div className="trend-stat-track" aria-hidden="true">
            <div className="trend-stat-fill" style={{ width: `${Math.max(4, Math.round(fraction * 100))}%` }} />
          </div>
        )}
        {compact ? null : <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{chartPlaceholder("single", `${xNoun}s`)}</p>}
      </div>
    );
  }

  const scales = width > 0 ? makeScales(series, width, height, pad, invertY) : null;
  const sparse = series.status === "sparse";
  const caption = compact ? null : gapCaption(series);
  const peak = series.stats.peak;
  const low = series.stats.low;

  type Hit = { key: string; x: number; y: number; text: string };
  const hits: Hit[] = scales
    ? [
        ...series.played.map((p) => ({ key: `p${p.x}`, x: scales.x(p.x), y: scales.y(p.y), text: `${p.label ?? formatX(p.x)} · ${formatY(p.y)}${unit ? ` ${unit}` : ""}` })),
        ...series.gaps.map((g) => ({ key: `g${g.x}`, x: scales.x(g.x), y: scales.y(g.y), text: `${g.label ?? formatX(g.x)} · ${GAP_LABEL[g.kind]}` })),
      ]
    : [];
  const active = hits.find((h) => h.key === selected) ?? null;

  return (
    <div className="flex flex-col gap-1" data-testid={testId ?? "trend-chart"} data-status={series.status}>
      <p className="sr-only">{summary}</p>
      <div ref={ref} className="trend-chart" style={{ height }}>
        {scales ? (
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
            <defs>
              <linearGradient id={`tc-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            {compact ? null : (
              <>
                {series.yTicks.map((t) => (
                  <g key={t}>
                    <line x1={scales.plot.left} x2={scales.plot.right} y1={scales.y(t)} y2={scales.y(t)} stroke="var(--color-border)" strokeOpacity={0.6} />
                    <text x={scales.plot.left - 6} y={scales.y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-text-muted)">{formatTick(t)}</text>
                  </g>
                ))}
                {series.xTicks.map((t) => (
                  <text key={t} x={scales.x(t)} y={height - 6} textAnchor={t === series.xDomain[0] && !sparse ? "start" : t === series.xDomain[1] && !sparse ? "end" : "middle"} fontSize={10} fill="var(--color-text-muted)">{formatX(t)}</text>
                ))}
              </>
            )}
            {series.band.length > 1 ? <path d={bandPathFor(series.band, scales)} fill="var(--color-accent)" fillOpacity={0.16} /> : null}
            {series.band.length > 1 ? (
              <path d={linePath(series.band.map((b) => ({ x: scales.x(b.x), y: scales.y(b.mean) })), smooth)} fill="none" stroke="var(--color-accent)" strokeOpacity={0.7} strokeWidth={1.5} strokeDasharray="4 3" />
            ) : null}
            {series.bridges.map((b) => (
              <path key={`b${b.from.x}`} d={`M ${scales.x(b.from.x)} ${scales.y(b.from.y)} L ${scales.x(b.to.x)} ${scales.y(b.to.y)}`} fill="none" stroke="var(--color-text-muted)" strokeOpacity={0.75} strokeWidth={1.5} strokeDasharray="3 4" strokeLinecap="round" data-testid="trend-bridge" />
            ))}
            {compact
              ? null
              : series.segments
                  .filter((s) => s.length > 1)
                  .map((s) => <path key={`a${s[0].x}`} d={areaPath(s.map((p) => ({ x: scales.x(p.x), y: scales.y(p.y) })), scales.plot.bottom, smooth)} fill={`url(#tc-${gradientId})`} />)}
            {series.segments
              .filter((s) => s.length > 1)
              .map((s) => (
                <path key={`l${s[0].x}`} className="trend-draw" pathLength={1} d={linePath(s.map((p) => ({ x: scales.x(p.x), y: scales.y(p.y) })), smooth)} fill="none" stroke="var(--color-accent)" strokeWidth={compact ? 1.75 : 2} strokeLinecap="round" strokeLinejoin="round" />
              ))}
            {series.gaps.map((g) => (
              <circle key={`gm${g.x}`} cx={scales.x(g.x)} cy={scales.y(g.y)} r={compact ? 2.5 : 3.5} fill="var(--color-bg)" stroke="var(--color-text-muted)" strokeWidth={1.5} data-testid="trend-gap-marker" />
            ))}
            {series.played.map((p, i) => {
              const isLast = i === series.played.length - 1;
              if (compact && !isLast) return null;
              const custom = pointColor?.(p, { peak, low });
              const isPeak = peak && p.x === peak.x && series.played.length > 3;
              return <circle key={`d${p.x}`} cx={scales.x(p.x)} cy={scales.y(p.y)} r={sparse ? 5 : isPeak || compact ? 4.5 : 3} fill={custom ?? (isPeak ? "var(--color-accent-strong)" : "var(--color-accent)")} stroke="var(--color-surface-secondary)" strokeWidth={1} />;
            })}
            {sparse && !compact
              ? series.played.map((p) => (
                  <text key={`v${p.x}`} x={scales.x(p.x)} y={scales.y(p.y) - 10} textAnchor="middle" fontSize={11} fontWeight={700} fill="var(--color-text-primary)">{formatY(p.y)}</text>
                ))
              : null}
            {active ? <circle cx={active.x} cy={active.y} r={7} fill="none" stroke="var(--color-text-primary)" strokeWidth={2} /> : null}
            {hits.map((h) => (
              <circle
                key={h.key}
                className="trend-hit"
                cx={h.x}
                cy={h.y}
                r={14}
                tabIndex={0}
                role="button"
                aria-label={h.text}
                onClick={() => setSelected((cur) => (cur === h.key ? null : h.key))}
                onMouseEnter={() => setSelected(h.key)}
                onMouseLeave={() => setSelected(null)}
                onFocus={() => setSelected(h.key)}
                onBlur={() => setSelected(null)}
              />
            ))}
          </svg>
        ) : null}
        {active ? (
          <div className="trend-tooltip" role="status" style={{ left: Math.min(Math.max(active.x - 70, 0), Math.max(width - 140, 0)), top: Math.max(active.y - 36, 0) }}>
            {active.text}
          </div>
        ) : null}
      </div>
      {caption ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{caption}</p> : null}
    </div>
  );
}

// Shared (web + mobile twin, byte-identical): the data side of EVERY trend chart.
// One module turns "rows of x/y where y may be missing" into something a chart can draw
// without ever leaving a blank hole or a lone dot:
//   - a missing / bye / injured week is a GAP: the line breaks into solid runs, a dashed
//     bridge crosses the gap and a muted hollow marker sits on it (never an empty area);
//   - one played point is a "single" status: the chart shows a labelled stat instead of a dot;
//   - two or three points are "sparse": direct value labels and wider dots, no axis noise;
//   - axes use nice ticks, optional zero baseline, optional clamp (ratings 0-99);
//   - smoothing is monotone cubic, so a curve never overshoots the data;
//   - an optional projection band (floor / ceiling / mean) shares the same scales.
// Components (web ui/TrendChart.tsx, mobile components/TrendChart.tsx) only draw the result.

export type GapKind = "missing" | "bye" | "injured";

/** One input row. y === null means nothing was recorded for this x (a gap), whatever the reason. */
export interface ChartInputPoint {
  x: number;
  y: number | null;
  /** Why y is missing; ignored when y is set. Defaults to "missing". */
  gap?: GapKind;
  /** Optional x label for tooltips (e.g. "Wk 4", "Nov 3"). */
  label?: string;
}

export interface ChartBandPoint {
  x: number;
  mean: number;
  floor: number;
  ceiling: number;
}

export interface PrepareOptions {
  /** Always include 0 in the y domain (points, counts). Default false. */
  includeZero?: boolean;
  /** Extra room above and below the data, in y units, before clamping. Default 0. */
  yPad?: number;
  /** Hard limits for the y domain, e.g. [0, 99] for a rating. */
  clamp?: [number, number] | null;
  /** Exact y domain (a rank chart is always 1 to the team count); ticks are its ends plus nice ones inside. */
  yDomain?: [number, number] | null;
  /** Desired tick count for the y axis. Default 4. */
  yTickCount?: number;
  /** Most x ticks to show. Default 6. */
  maxXTicks?: number;
  /** Projection band drawn behind / after the played data. */
  band?: readonly ChartBandPoint[] | null;
}

export interface ChartPoint {
  x: number;
  y: number;
  label?: string;
}

export interface ChartGap {
  x: number;
  /** Where the muted marker sits: on the bridge, or level with the nearest played point at the ends. */
  y: number;
  kind: GapKind;
  /** True when the marker sits between two played points (a dashed bridge crosses it). */
  between: boolean;
  label?: string;
}

export interface ChartBridge {
  from: ChartPoint;
  to: ChartPoint;
}

export type ChartStatus = "empty" | "single" | "sparse" | "ready";

export interface PreparedSeries {
  /** empty: nothing to draw. single: one played point and no projection, show a stat. sparse: 2-3 points. ready: 4+ (or any with a projection). */
  status: ChartStatus;
  played: ChartPoint[];
  /** Runs of consecutive played points: each is drawn as one solid line. */
  segments: ChartPoint[][];
  /** Dashed spans across gap rows between two played points. */
  bridges: ChartBridge[];
  gaps: ChartGap[];
  band: ChartBandPoint[];
  xDomain: [number, number];
  yDomain: [number, number];
  yTicks: number[];
  xTicks: number[];
  stats: { count: number; min: number; max: number; average: number; last: number | null; peak: ChartPoint | null; low: ChartPoint | null };
}

const EMPTY: PreparedSeries = {
  status: "empty",
  played: [],
  segments: [],
  bridges: [],
  gaps: [],
  band: [],
  xDomain: [0, 1],
  yDomain: [0, 1],
  yTicks: [0, 1],
  xTicks: [],
  stats: { count: 0, min: 0, max: 0, average: 0, last: null, peak: null, low: null },
};

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** 1-2-5 step for a span split into about `count` intervals. */
export function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const pow = 10 ** Math.floor(Math.log10(raw));
  const f = raw / pow;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nice * pow;
}

/** Round the domain out to nice tick values (never beyond `clamp`). */
export function niceDomain(lo: number, hi: number, count: number, clamp?: [number, number] | null): { domain: [number, number]; ticks: number[] } {
  let a = lo;
  let b = hi;
  if (b - a < 1e-9) {
    const pad = Math.max(1, Math.abs(a) * 0.1);
    a -= pad;
    b += pad;
  }
  const step = niceStep(b - a, count);
  let start = Math.floor(a / step) * step;
  let end = Math.ceil(b / step) * step;
  if (clamp) {
    start = Math.max(start, clamp[0]);
    end = Math.min(end, clamp[1]);
    if (end - start < 1e-9) end = start + step;
  }
  const ticks: number[] = [];
  for (let t = start; t <= end + step * 1e-6; t += step) ticks.push(Math.round(t * 1e6) / 1e6);
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks };
}

/** An exact domain: its two ends plus nice ticks strictly inside (never crowding an end). */
export function fixedDomain(domain: [number, number], count: number): { domain: [number, number]; ticks: number[] } {
  const [lo, hi] = domain[0] <= domain[1] ? domain : [domain[1], domain[0]];
  const step = niceStep(Math.max(hi - lo, 1e-9), count);
  const ticks = [lo];
  for (let t = Math.ceil(lo / step) * step; t < hi - step * 0.4; t += step) if (t > lo + step * 0.4) ticks.push(Math.round(t * 1e6) / 1e6);
  ticks.push(hi);
  return { domain: [lo, hi], ticks };
}

/** Thin an ordered list of x values to at most `max` evenly stepped ticks, starting at the first. */
export function thinTicks(xs: readonly number[], max: number): number[] {
  if (xs.length <= max) return [...xs];
  const step = Math.ceil((xs.length - 1) / (max - 1));
  return xs.filter((_, i) => i % step === 0);
}

export function prepareSeries(input: readonly ChartInputPoint[], options: PrepareOptions = {}): PreparedSeries {
  const rows = [...input].filter((r) => isNum(r.x)).sort((a, b) => a.x - b.x);
  const band = [...(options.band ?? [])].filter((b) => isNum(b.x) && isNum(b.mean) && isNum(b.floor) && isNum(b.ceiling)).sort((a, b) => a.x - b.x);
  const playedRows = rows.filter((r) => isNum(r.y));
  if (playedRows.length === 0 && band.length === 0) return EMPTY;

  // Gaps before the first played row or after the last one are real (an injured week at the start of a
  // season) but a band row is not a gap. Trailing rows past the last played x are only gaps when the
  // caller put them there on purpose (a bye is, a week that has not happened yet should be left out).
  const played: ChartPoint[] = playedRows.map((r) => ({ x: r.x, y: r.y as number, label: r.label }));
  const segments: ChartPoint[][] = [];
  const bridges: ChartBridge[] = [];
  const gaps: ChartGap[] = [];
  let run: ChartPoint[] = [];
  let pendingGapRows: ChartInputPoint[] = [];
  let lastPlayed: ChartPoint | null = null;
  const flushLeadingGaps = (next: ChartPoint) => {
    for (const g of pendingGapRows) gaps.push({ x: g.x, y: next.y, kind: g.gap ?? "missing", between: false, label: g.label });
    pendingGapRows = [];
  };
  for (const r of rows) {
    if (isNum(r.y)) {
      const pt: ChartPoint = { x: r.x, y: r.y, label: r.label };
      if (!lastPlayed) {
        flushLeadingGaps(pt);
        run = [pt];
      } else if (pendingGapRows.length > 0) {
        segments.push(run);
        run = [pt];
        bridges.push({ from: lastPlayed, to: pt });
        for (const g of pendingGapRows) {
          const t = (g.x - lastPlayed.x) / (pt.x - lastPlayed.x || 1);
          gaps.push({ x: g.x, y: lastPlayed.y + (pt.y - lastPlayed.y) * t, kind: g.gap ?? "missing", between: true, label: g.label });
        }
        pendingGapRows = [];
      } else {
        run.push(pt);
      }
      lastPlayed = pt;
    } else {
      pendingGapRows.push(r);
    }
  }
  if (run.length) segments.push(run);
  if (lastPlayed) for (const g of pendingGapRows) gaps.push({ x: g.x, y: lastPlayed.y, kind: g.gap ?? "missing", between: false, label: g.label });

  const ys = [...played.map((p) => p.y), ...band.flatMap((b) => [b.floor, b.ceiling, b.mean])];
  const yPad = options.yPad ?? 0;
  const lo0 = Math.min(...ys) - yPad;
  const hi0 = Math.max(...ys) + yPad;
  const fixed = options.yDomain ?? null;
  const { domain: yDomain, ticks: yTicks } = fixed ? fixedDomain(fixed, options.yTickCount ?? 4) : niceDomain(options.includeZero ? Math.min(0, lo0) : lo0, options.includeZero ? Math.max(0, hi0) : hi0, options.yTickCount ?? 4, options.clamp);

  const xs = [...rows.map((r) => r.x), ...band.map((b) => b.x)];
  const xDomain: [number, number] = [Math.min(...xs), Math.max(...xs)];
  if (xDomain[1] === xDomain[0]) xDomain[1] = xDomain[0] + 1;
  const xTicks = thinTicks([...new Set(xs)].sort((a, b) => a - b), options.maxXTicks ?? 6);

  const peak = played.length ? played.reduce((best, p) => (p.y > best.y ? p : best), played[0]) : null;
  const low = played.length ? played.reduce((best, p) => (p.y < best.y ? p : best), played[0]) : null;
  const total = played.reduce((sum, p) => sum + p.y, 0);
  const stats = {
    count: played.length,
    min: low ? low.y : 0,
    max: peak ? peak.y : 0,
    average: played.length ? total / played.length : 0,
    last: played.length ? played[played.length - 1].y : null,
    peak,
    low,
  };

  const hasBand = band.length > 0;
  const status: ChartStatus = played.length === 1 && !hasBand ? "single" : played.length === 0 && !hasBand ? "empty" : played.length <= 3 && !hasBand ? "sparse" : "ready";
  return { status, played, segments, bridges, gaps, band, xDomain, yDomain, yTicks, xTicks, stats };
}

/** Weekly rows -> chart rows: every week from the first to the last reported one, absent weeks explicit gaps
 * (a bye when listed, otherwise "missing"). Never extends past the latest reported week (that week has not
 * happened yet, it is not a gap). */
export function weeklyGapRows(weeks: readonly { week: number; points: number | null }[], byeWeeks: readonly number[] = [], prefix = "Wk"): ChartInputPoint[] {
  const valid = weeks.filter((w) => isNum(w.week));
  if (valid.length === 0) return [];
  const byWeek = new Map(valid.map((w) => [w.week, w.points]));
  const bye = new Set(byeWeeks);
  const first = Math.min(...valid.map((w) => w.week));
  const last = Math.max(...valid.map((w) => w.week));
  const rows: ChartInputPoint[] = [];
  for (let week = first; week <= last; week += 1) {
    const y = byWeek.get(week);
    rows.push({ x: week, y: isNum(y) ? y : null, gap: bye.has(week) ? "bye" : "missing", label: `${prefix} ${week}` });
  }
  return rows;
}

/* ---------------- geometry (shared so web and mobile draw the same curve) ---------------- */

export interface ChartPad {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface ChartScales {
  x: (v: number) => number;
  y: (v: number) => number;
  plot: { left: number; right: number; top: number; bottom: number; width: number; height: number };
}

/** `invert` puts the domain's low end at the top (a rank chart: #1 on top). */
export function makeScales(series: Pick<PreparedSeries, "xDomain" | "yDomain">, width: number, height: number, pad: ChartPad, invert = false): ChartScales {
  const left = pad.left;
  const right = Math.max(left + 1, width - pad.right);
  const top = pad.top;
  const bottom = Math.max(top + 1, height - pad.bottom);
  const [x0, x1] = series.xDomain;
  const [y0, y1] = series.yDomain;
  return {
    x: (v) => left + ((v - x0) / (x1 - x0 || 1)) * (right - left),
    y: (v) => (invert ? top + ((v - y0) / (y1 - y0 || 1)) * (bottom - top) : bottom - ((v - y0) / (y1 - y0 || 1)) * (bottom - top)),
    plot: { left, right, top, bottom, width: right - left, height: bottom - top },
  };
}

const f = (n: number) => Math.round(n * 100) / 100;

/** Monotone cubic (Fritsch-Carlson) through pixel points: smooth, and never overshoots the data. */
export function linePath(pts: readonly { x: number; y: number }[], smooth = true): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M ${f(pts[0].x)} ${f(pts[0].y)}`;
  if (!smooth || pts.length === 2) return pts.map((p, i) => `${i === 0 ? "M" : "L"} ${f(p.x)} ${f(p.y)}`).join(" ");
  const n = pts.length;
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i += 1) {
    dx.push(pts[i + 1].x - pts[i].x || 1e-6);
    slope.push((pts[i + 1].y - pts[i].y) / dx[i]);
  }
  const m: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i += 1) m.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  m.push(slope[n - 2]);
  for (let i = 0; i < n - 1; i += 1) {
    if (slope[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / slope[i];
    const b = m[i + 1] / slope[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * slope[i];
      m[i + 1] = t * b * slope[i];
    }
  }
  let d = `M ${f(pts[0].x)} ${f(pts[0].y)}`;
  for (let i = 0; i < n - 1; i += 1) {
    const h = dx[i] / 3;
    d += ` C ${f(pts[i].x + h)} ${f(pts[i].y + m[i] * h)} ${f(pts[i + 1].x - h)} ${f(pts[i + 1].y - m[i + 1] * h)} ${f(pts[i + 1].x)} ${f(pts[i + 1].y)}`;
  }
  return d;
}

/** The line closed down to the baseline: the gradient fill under one solid run. */
export function areaPath(pts: readonly { x: number; y: number }[], baselineY: number, smooth = true): string {
  if (pts.length < 2) return "";
  return `${linePath(pts, smooth)} L ${f(pts[pts.length - 1].x)} ${f(baselineY)} L ${f(pts[0].x)} ${f(baselineY)} Z`;
}

/** Floor to ceiling polygon for a projection band, in pixel space. */
export function bandPathFor(band: readonly ChartBandPoint[], scales: ChartScales): string {
  if (band.length < 2) return "";
  const up = band.map((b) => `${f(scales.x(b.x))} ${f(scales.y(b.ceiling))}`);
  const down = [...band].reverse().map((b) => `${f(scales.x(b.x))} ${f(scales.y(b.floor))}`);
  return `M ${up.join(" L ")} L ${down.join(" L ")} Z`;
}

/* ---------------- copy ---------------- */

export const GAP_LABEL: Record<GapKind, string> = { missing: "No game", bye: "Bye week", injured: "Injured" };

export function gapCaption(series: Pick<PreparedSeries, "gaps">): string | null {
  if (series.gaps.length === 0) return null;
  const kinds = new Set(series.gaps.map((g) => g.kind));
  if (kinds.size === 1) return `Dashed: ${GAP_LABEL[[...kinds][0]].toLowerCase()}`;
  return "Dashed: bye, injured or missed weeks";
}

export function chartPlaceholder(status: ChartStatus, noun = "weeks"): string | null {
  if (status === "empty") return `No ${noun} recorded yet`;
  if (status === "single") return `Not enough ${noun} yet for a trend`;
  return null;
}

/** Fill fraction (0-1) of the mini bar a single value gets: against 0 up to the nice top of the domain. */
export function singleBarFraction(value: number, yDomain: readonly [number, number]): number {
  const span = yDomain[1] - yDomain[0];
  if (span <= 0) return 0;
  return Math.min(1, Math.max(0, (value - yDomain[0]) / span));
}

export function formatTick(v: number): string {
  return Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : v.toFixed(1);
}

/** One sentence for assistive tech: what the chart says, without the picture. */
export function chartSummary(series: PreparedSeries, name: string, unit: string, xNoun = "week", fmt: (v: number) => string = (v) => v.toFixed(1)): string {
  if (series.status === "empty") return `${name}: no data yet.`;
  const s = series.stats;
  const gaps = series.gaps.length ? ` ${series.gaps.length} ${xNoun}${series.gaps.length === 1 ? "" : "s"} with no data.` : "";
  if (series.status === "single" && series.played[0]) return `${name}: one ${xNoun} so far, ${fmt(series.played[0].y)} ${unit}.`;
  return `${name}: ${s.count} ${xNoun}${s.count === 1 ? "" : "s"}, average ${fmt(s.average)} ${unit}, high ${fmt(s.max)}, low ${fmt(s.min)}, latest ${fmt(s.last ?? 0)}.${gaps}`;
}

import React, { useMemo, useState } from 'react';
import { LayoutChangeEvent, Pressable, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop, Text as SvgText } from 'react-native-svg';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
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
} from '../lib/chartSeries';
import { radii, spacing, typography, type ThemeColors } from '../theme';

/**
 * THE trend chart on mobile: every line / area chart in the app goes through this one component, on the same
 * lib/chartSeries.ts as the web twin (web-next/src/components/ui/TrendChart.tsx), so gaps and lone points look
 * the same everywhere:
 *   - bye / missed / injured weeks break the line: dashed bridge + muted hollow marker, never a blank hole;
 *   - one played point renders a labelled stat with a mini bar, not a dot; no data renders a short sentence;
 *   - two or three points get wide spacing, bigger dots and direct value labels;
 *   - tap a point for a tooltip; `compact` is the axis-free sparkline; monotone smoothing.
 * Nothing animates, so reduced motion is satisfied by construction. Colors come from the theme only.
 */
export interface TrendChartProps {
  points: readonly ChartInputPoint[];
  band?: readonly ChartBandPoint[] | null;
  name: string;
  unit?: string;
  xNoun?: string;
  formatX?: (x: number) => string;
  formatY?: (y: number) => string;
  variant?: 'full' | 'compact';
  height?: number;
  includeZero?: boolean;
  yPad?: number;
  clamp?: [number, number] | null;
  yDomain?: [number, number] | null;
  yTickCount?: number;
  invertY?: boolean;
  smooth?: boolean;
  emptyText?: string;
  pointColor?: (point: ChartPoint, ctx: { peak: ChartPoint | null; low: ChartPoint | null }, colors: ThemeColors) => string | undefined;
  testID?: string;
}

const FULL_PAD: ChartPad = { top: 14, right: 10, bottom: 22, left: 30 };
const COMPACT_PAD: ChartPad = { top: 6, right: 6, bottom: 6, left: 6 };
const TOOLTIP_WIDTH = 140;
const DEFAULT_FORMAT = (v: number) => v.toFixed(1);

export default function TrendChart(props: TrendChartProps) {
  const {
    points,
    band = null,
    name,
    unit = '',
    xNoun = 'week',
    formatX = (x: number) => String(x),
    formatY = DEFAULT_FORMAT,
    variant = 'full',
    includeZero = false,
    yPad = 0,
    clamp = null,
    yDomain = null,
    yTickCount = 4,
    invertY = false,
    smooth = true,
    emptyText,
    pointColor,
    testID,
  } = props;
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const compact = variant === 'compact';
  const height = props.height ?? (compact ? 44 : 160);
  const pad = compact ? COMPACT_PAD : FULL_PAD;
  const [width, setWidth] = useState(0);
  // The selection belongs to one `points` array: new data drops it.
  const [pick, setPick] = useState<{ points: readonly ChartInputPoint[]; key: string | null }>({ points, key: null });
  const selected = pick.points === points ? pick.key : null;
  const setSelected = (next: string | null | ((cur: string | null) => string | null)) => setPick({ points, key: typeof next === 'function' ? next(selected) : next });

  const options: PrepareOptions = { includeZero, yPad, clamp, yDomain, yTickCount, band };
  const series = useMemo(() => prepareSeries(points, options), [points, band, includeZero, yPad, clamp, yDomain, yTickCount]); // eslint-disable-line react-hooks/exhaustive-deps
  const summary = chartSummary(series, name, unit, xNoun, formatY);

  if (series.status === 'empty') {
    return (
      <AppText style={styles.empty} testID={testID ? `${testID}-empty` : undefined}>
        {emptyText ?? chartPlaceholder('empty', `${xNoun}s`)}
      </AppText>
    );
  }
  if (series.status === 'single' && series.played[0]) {
    const only = series.played[0];
    const fraction = singleBarFraction(only.y, [Math.min(0, series.yDomain[0]), series.yDomain[1]]);
    return (
      <View style={styles.stat} accessible accessibilityLabel={summary} testID={testID ? `${testID}-single` : 'trend-chart-single'}>
        <View style={styles.statRow}>
          <AppText style={styles.statValue}>
            {formatY(only.y)}
            {unit ? <AppText style={styles.statUnit}> {unit}</AppText> : null}
          </AppText>
          <AppText style={styles.statLabel}>{only.label ?? formatX(only.x)}</AppText>
        </View>
        {compact ? null : (
          <>
            <View style={styles.statTrack}>
              <View style={[styles.statFill, { width: `${Math.max(4, Math.round(fraction * 100))}%` }]} />
            </View>
            <AppText style={styles.caption}>{chartPlaceholder('single', `${xNoun}s`)}</AppText>
          </>
        )}
      </View>
    );
  }

  const scales = width > 0 ? makeScales(series, width, height, pad, invertY) : null;
  const sparse = series.status === 'sparse';
  const caption = compact ? null : gapCaption(series);
  const { peak, low } = series.stats;

  type Hit = { key: string; x: number; y: number; text: string };
  const hits: Hit[] = scales
    ? [
        ...series.played.map((p) => ({ key: `p${p.x}`, x: scales.x(p.x), y: scales.y(p.y), text: `${p.label ?? formatX(p.x)} · ${formatY(p.y)}${unit ? ` ${unit}` : ''}` })),
        ...series.gaps.map((g) => ({ key: `g${g.x}`, x: scales.x(g.x), y: scales.y(g.y), text: `${g.label ?? formatX(g.x)} · ${GAP_LABEL[g.kind]}` })),
      ]
    : [];
  const active = hits.find((h) => h.key === selected) ?? null;
  const toPx = (pts: ChartPoint[]) => (scales ? pts.map((p) => ({ x: scales.x(p.x), y: scales.y(p.y) })) : []);

  return (
    <View testID={testID ?? 'trend-chart'} accessibilityLabel={summary}>
      <View onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)} style={{ height }}>
        {scales ? (
          <Svg width={width} height={height}>
            <Defs>
              <LinearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={colors.accent} stopOpacity={0.35} />
                <Stop offset="1" stopColor={colors.accent} stopOpacity={0} />
              </LinearGradient>
            </Defs>
            {compact ? null : (
              <>
                {series.yTicks.map((t) => (
                  <React.Fragment key={t}>
                    <Line x1={scales.plot.left} x2={scales.plot.right} y1={scales.y(t)} y2={scales.y(t)} stroke={colors.border} strokeOpacity={0.6} strokeWidth={1} />
                    <SvgText x={scales.plot.left - 6} y={scales.y(t) + 3} textAnchor="end" fontSize={10} fill={colors.textTertiary}>
                      {formatTick(t)}
                    </SvgText>
                  </React.Fragment>
                ))}
                {series.xTicks.map((t) => (
                  <SvgText key={t} x={scales.x(t)} y={height - 6} textAnchor="middle" fontSize={10} fill={colors.textTertiary}>
                    {formatX(t)}
                  </SvgText>
                ))}
              </>
            )}
            {series.band.length > 1 ? <Path d={bandPathFor(series.band, scales)} fill={colors.accent} fillOpacity={0.16} /> : null}
            {series.band.length > 1 ? (
              <Path d={linePath(series.band.map((b) => ({ x: scales.x(b.x), y: scales.y(b.mean) })), smooth)} fill="none" stroke={colors.accent} strokeOpacity={0.7} strokeWidth={1.5} strokeDasharray="4 3" />
            ) : null}
            {series.bridges.map((b) => (
              <Line key={`b${b.from.x}`} x1={scales.x(b.from.x)} y1={scales.y(b.from.y)} x2={scales.x(b.to.x)} y2={scales.y(b.to.y)} stroke={colors.textTertiary} strokeOpacity={0.75} strokeWidth={1.5} strokeDasharray="3 4" strokeLinecap="round" />
            ))}
            {compact
              ? null
              : series.segments.filter((s) => s.length > 1).map((s) => <Path key={`a${s[0].x}`} d={areaPath(toPx(s), scales.plot.bottom, smooth)} fill="url(#trendFill)" />)}
            {series.segments.filter((s) => s.length > 1).map((s) => (
              <Path key={`l${s[0].x}`} d={linePath(toPx(s), smooth)} fill="none" stroke={colors.accent} strokeWidth={compact ? 1.75 : 2} strokeLinecap="round" strokeLinejoin="round" />
            ))}
            {series.gaps.map((g) => (
              <Circle key={`gm${g.x}`} cx={scales.x(g.x)} cy={scales.y(g.y)} r={compact ? 2.5 : 3.5} fill={colors.background} stroke={colors.textTertiary} strokeWidth={1.5} />
            ))}
            {series.played.map((p, i) => {
              const isLast = i === series.played.length - 1;
              if (compact && !isLast) return null;
              const isPeak = peak && p.x === peak.x && series.played.length > 3;
              return <Circle key={`d${p.x}`} cx={scales.x(p.x)} cy={scales.y(p.y)} r={sparse ? 5 : isPeak || compact ? 4.5 : 3} fill={pointColor?.(p, { peak, low }, colors) ?? colors.accent} stroke={colors.surface} strokeWidth={1} />;
            })}
            {sparse && !compact
              ? series.played.map((p) => (
                  <SvgText key={`v${p.x}`} x={scales.x(p.x)} y={scales.y(p.y) - 10} textAnchor="middle" fontSize={11} fontWeight="700" fill={colors.textPrimary}>
                    {formatY(p.y)}
                  </SvgText>
                ))
              : null}
            {active ? <Circle cx={active.x} cy={active.y} r={7} fill="none" stroke={colors.textPrimary} strokeWidth={2} /> : null}
          </Svg>
        ) : null}
        {hits.map((h) => (
          <Pressable
            key={h.key}
            accessibilityRole="button"
            accessibilityLabel={h.text}
            onPress={() => setSelected((cur) => (cur === h.key ? null : h.key))}
            hitSlop={8}
            style={{ position: 'absolute', left: h.x - 14, top: h.y - 14, width: 28, height: 28 }}
          />
        ))}
        {active ? (
          <View pointerEvents="none" style={[styles.tooltip, { left: Math.min(Math.max(active.x - TOOLTIP_WIDTH / 2, 0), Math.max(width - TOOLTIP_WIDTH, 0)), top: Math.max(active.y - 36, 0) }]}>
            <AppText style={styles.tooltipText}>{active.text}</AppText>
          </View>
        ) : null}
      </View>
      {caption ? <AppText style={styles.caption}>{caption}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return {
    empty: { ...typography.bodyMuted, color: colors.textSecondary, textAlign: 'center' as const, paddingVertical: spacing.lg },
    caption: { ...typography.caption, color: colors.textTertiary },
    stat: { gap: spacing.xs, padding: spacing.sm, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
    statRow: { flexDirection: 'row' as const, alignItems: 'baseline' as const, justifyContent: 'space-between' as const },
    statValue: { fontSize: 22, fontWeight: '800' as const, color: colors.textPrimary },
    statUnit: { fontSize: 12, fontWeight: '700' as const, color: colors.textTertiary },
    statLabel: { ...typography.caption, fontWeight: '700' as const, color: colors.textTertiary, textTransform: 'uppercase' as const },
    statTrack: { height: 6, borderRadius: 999, backgroundColor: colors.border, overflow: 'hidden' as const },
    statFill: { height: 6, borderRadius: 999, backgroundColor: colors.accent },
    tooltip: {
      position: 'absolute' as const,
      width: TOOLTIP_WIDTH,
      backgroundColor: colors.backgroundElevated,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: 6,
      paddingVertical: 4,
      paddingHorizontal: 6,
      alignItems: 'center' as const,
    },
    tooltipText: { ...typography.caption, fontWeight: '700' as const, color: colors.textPrimary },
  };
}

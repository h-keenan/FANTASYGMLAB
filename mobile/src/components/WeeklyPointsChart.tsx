import React, { useEffect, useMemo, useState } from 'react';
import { LayoutChangeEvent, Pressable, View } from 'react-native';
import AppText from './AppText';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

import type { WeeklyStatPoint } from '../lib/api';
import { buildWeeklyChartRows, type WeeklyProjectionPoint } from '../lib/weeklyProjection';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, typography, type ThemeColors } from '../theme';

const HEIGHT = 140;
const TOP_PAD = 16;
const BOTTOM_PAD = 22;
const SIDE_PAD = 8;
// Reserves room on the left for the max/min value labels (coridian_: "the
// points per week graph needs to have the points on the y-axis") — the
// x-axis week labels below already have their own row, so these two values
// are the only y-axis markers, placed right at the high/low dots rather
// than a full gridline scale.
const LEFT_PAD = 30;
const FILL_GRADIENT_ID = 'weeklyPointsFill';

function buildPath(points: Array<{ x: number; y: number }>): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
}

/** Same line as buildPath, closed down to the baseline and back along it —
 * the shape a gradient gets clipped to for the "area chart" fill under the
 * line, not just a bare stroke. */
function buildAreaPath(points: Array<{ x: number; y: number }>, baselineY: number): string {
  if (points.length === 0) return '';
  const line = buildPath(points);
  const last = points[points.length - 1];
  const first = points[0];
  return `${line} L ${last.x} ${baselineY} L ${first.x} ${baselineY} Z`;
}

/** A player's fantasy points across the weeks of one season — Player
 * Detail's "is this guy trending up or down" chart, requested alongside the
 * snap% bar since neither existed before (the season card only ever showed
 * one aggregate PPG number). */
export default function WeeklyPointsChart({
  weeks,
  projection = null,
  pointsLabel = 'pts',
  emptyText,
  xLabel = 'Week',
}: {
  weeks: WeeklyStatPoint[];
  /** Optional rest-of-season projection drawn as a band behind the played weeks (Fantasy Sim). */
  projection?: readonly WeeklyProjectionPoint[] | null;
  pointsLabel?: string;
  emptyText?: string;
  /** What the x axis counts (the development curve plots 'Year'). */
  xLabel?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [width, setWidth] = useState(0);
  // coridian_: "you need to be able to tap on points on the graph to see
  // what the value is" — the dots themselves are too small a target to tap
  // reliably, so each gets its own larger invisible touch area (below).
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  useEffect(() => {
    setSelectedWeek(null);
  }, [weeks]);

  const hasProjection = Boolean(projection && projection.length > 0);
  const played = weeks.filter((week) => week.fantasy_points_ppr != null);
  if (played.length === 0 && !hasProjection) {
    return <AppText style={styles.empty}>{emptyText ?? 'No weekly points recorded for this season yet.'}</AppText>;
  }
  // With a projection the x axis is the real week range (played weeks and the weeks ahead); without one it is
  // exactly the old chart: the played weeks, evenly spaced.
  const rows = hasProjection
    ? buildWeeklyChartRows(
        played.map((w) => ({ week: w.week, points: w.fantasy_points_ppr })),
        projection,
      )
    : played.map((w) => ({ week: w.week, actual: w.fantasy_points_ppr, mean: null, floor: null, ceiling: null }));

  const values = played.map((week) => week.fantasy_points_ppr as number);
  const ceilings = rows.map((r) => r.ceiling).filter((v): v is number => v != null);
  const maxValue = Math.max(...values, ...ceilings, 1);
  const minValue = Math.min(...values, 0);
  const range = maxValue - minValue || 1;
  const plotWidth = Math.max(width - LEFT_PAD - SIDE_PAD, 1);
  const plotHeight = HEIGHT - TOP_PAD - BOTTOM_PAD;
  const step = rows.length > 1 ? plotWidth / (rows.length - 1) : 0;
  const xAt = (index: number) => LEFT_PAD + (rows.length > 1 ? step * index : plotWidth / 2);
  const yAt = (value: number) => TOP_PAD + plotHeight - ((value - minValue) / range) * plotHeight;

  const points = rows
    .map((row, index) => ({ x: xAt(index), y: row.actual != null ? yAt(row.actual) : 0, week: row.week, value: row.actual }))
    .filter((point): point is { x: number; y: number; week: number; value: number } => point.value != null);
  const projRows = rows.map((row, index) => ({ x: xAt(index), row })).filter((r) => r.row.mean != null && r.row.floor != null && r.row.ceiling != null);
  const bandPath =
    projRows.length > 1
      ? `${projRows.map((r, i) => `${i === 0 ? 'M' : 'L'} ${r.x} ${yAt(r.row.ceiling as number)}`).join(' ')} ${[...projRows]
          .reverse()
          .map((r) => `L ${r.x} ${yAt(r.row.floor as number)}`)
          .join(' ')} Z`
      : '';
  const meanPath = projRows.length > 1 ? buildPath(projRows.map((r) => ({ x: r.x, y: yAt(r.row.mean as number) }))) : '';
  const maxY = TOP_PAD;
  const minY = TOP_PAD + plotHeight;
  const selectedTooltipPoint = points.find((point) => point.week === selectedWeek) ?? null;

  const onLayout = (event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width);

  return (
    <View onLayout={onLayout}>
      {width > 0 ? (
        <Svg width={width} height={HEIGHT}>
          <Defs>
            <LinearGradient id={FILL_GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.accent} stopOpacity={0.35} />
              <Stop offset="1" stopColor={colors.accent} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Line
            x1={LEFT_PAD}
            y1={TOP_PAD + plotHeight}
            x2={width - SIDE_PAD}
            y2={TOP_PAD + plotHeight}
            stroke={colors.border}
            strokeWidth={1}
          />
          {bandPath ? <Path d={bandPath} fill={colors.accent} fillOpacity={0.16} /> : null}
          {meanPath ? <Path d={meanPath} stroke={colors.accent} strokeOpacity={0.7} strokeWidth={1.5} strokeDasharray="4 3" fill="none" /> : null}
          {points.length > 0 ? <Path d={buildAreaPath(points, TOP_PAD + plotHeight)} fill={`url(#${FILL_GRADIENT_ID})`} /> : null}
          {points.length > 0 ? <Path d={buildPath(points)} stroke={colors.accent} strokeWidth={2} fill="none" /> : null}
          {points.map((point) => (
            <Circle
              key={point.week}
              cx={point.x}
              cy={point.y}
              r={point.week === selectedWeek ? 5.5 : 3.5}
              fill={
                point.value === Math.max(...values) ? colors.successBright : point.value === minValue ? colors.danger : colors.accent
              }
              stroke={point.week === selectedWeek ? colors.textPrimary : 'none'}
              strokeWidth={point.week === selectedWeek ? 2 : 0}
            />
          ))}
        </Svg>
      ) : null}
      {width > 0
        ? points.map((point) => (
            <Pressable
              key={point.week}
              onPress={() => setSelectedWeek((current) => (current === point.week ? null : point.week))}
              hitSlop={10}
              style={[styles.touchTarget, { left: point.x - 14, top: point.y - 14 }]}
            />
          ))
        : null}
      {selectedTooltipPoint ? (
        <View
          pointerEvents="none"
          style={[
            styles.tooltip,
            {
              left: Math.min(Math.max(selectedTooltipPoint.x - TOOLTIP_WIDTH / 2, 0), Math.max(width - TOOLTIP_WIDTH, 0)),
              top: Math.max(selectedTooltipPoint.y - 34, 0),
            },
          ]}
        >
          <AppText style={styles.tooltipText}>
            {xLabel} {selectedTooltipPoint.week} · {selectedTooltipPoint.value.toFixed(1)} {pointsLabel}
          </AppText>
        </View>
      ) : null}
      {width > 0 ? (
        <>
          <AppText style={[styles.axisLabel, styles.axisLabelHigh, { top: maxY - 7 }]}>{Math.round(maxValue)}</AppText>
          <AppText style={[styles.axisLabel, styles.axisLabelLow, { top: minY - 7 }]}>{Math.round(minValue)}</AppText>
        </>
      ) : null}
      <View style={styles.labelRow}>
        {(hasProjection ? rows.map((row, index) => ({ week: row.week, x: xAt(index) })).filter((_, i, all) => all.length <= 12 || i % 2 === 0) : points).map((point) => (
          <AppText
            key={point.week}
            style={[styles.weekLabel, { left: point.x - LABEL_WIDTH / 2 }]}
          >
            {point.week}
          </AppText>
        ))}
      </View>
    </View>
  );
}

const LABEL_WIDTH = 20;
const TOOLTIP_WIDTH = 100;

function createStyles(colors: ThemeColors) {
  return {
    empty: {
      ...typography.bodyMuted,
      color: colors.textSecondary,
      textAlign: 'center' as const,
      paddingVertical: spacing.lg,
    },
    // Absolutely positioned per-point at the same x the SVG drew its dot at —
    // a flexbox space-between row assumes even spacing across the full width,
    // which breaks down for a single point (centers the dot but left-aligns
    // its lone label) and isn't guaranteed to line up for any point count.
    labelRow: {
      height: 16,
      marginTop: spacing.xs,
    },
    weekLabel: {
      ...typography.caption,
      color: colors.textTertiary,
      position: 'absolute' as const,
      width: LABEL_WIDTH,
      textAlign: 'center' as const,
    },
    axisLabel: {
      ...typography.caption,
      fontWeight: '700' as const,
      position: 'absolute' as const,
      left: 0,
      width: LEFT_PAD - 4,
      textAlign: 'right' as const,
    },
    axisLabelHigh: { color: colors.successBright },
    axisLabelLow: { color: colors.danger },
    touchTarget: {
      position: 'absolute' as const,
      width: 28,
      height: 28,
    },
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
    tooltipText: {
      ...typography.caption,
      fontWeight: '700' as const,
      color: colors.textPrimary,
    },
  };
}

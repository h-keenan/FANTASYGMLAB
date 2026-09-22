import React, { useMemo, useState } from 'react';
import { LayoutChangeEvent, View } from 'react-native';
import AppText from './AppText';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

import type { WeeklyStatPoint } from '../lib/api';
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
export default function WeeklyPointsChart({ weeks }: { weeks: WeeklyStatPoint[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [width, setWidth] = useState(0);

  const played = weeks.filter((week) => week.fantasy_points_ppr != null);
  if (played.length === 0) {
    return <AppText style={styles.empty}>No weekly points recorded for this season yet.</AppText>;
  }

  const values = played.map((week) => week.fantasy_points_ppr as number);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = maxValue - minValue || 1;
  const plotWidth = Math.max(width - LEFT_PAD - SIDE_PAD, 1);
  const plotHeight = HEIGHT - TOP_PAD - BOTTOM_PAD;
  const step = played.length > 1 ? plotWidth / (played.length - 1) : 0;

  const points = played.map((week, index) => ({
    x: LEFT_PAD + (played.length > 1 ? step * index : plotWidth / 2),
    y: TOP_PAD + plotHeight - ((week.fantasy_points_ppr as number) - minValue) / range * plotHeight,
    week: week.week,
    value: week.fantasy_points_ppr as number,
  }));
  const maxY = TOP_PAD;
  const minY = TOP_PAD + plotHeight;

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
          <Path d={buildAreaPath(points, TOP_PAD + plotHeight)} fill={`url(#${FILL_GRADIENT_ID})`} />
          <Path d={buildPath(points)} stroke={colors.accent} strokeWidth={2} fill="none" />
          {points.map((point) => (
            <Circle
              key={point.week}
              cx={point.x}
              cy={point.y}
              r={3.5}
              fill={
                point.value === maxValue ? colors.successBright : point.value === minValue ? colors.danger : colors.accent
              }
            />
          ))}
        </Svg>
      ) : null}
      {width > 0 ? (
        <>
          <AppText style={[styles.axisLabel, styles.axisLabelHigh, { top: maxY - 7 }]}>{Math.round(maxValue)}</AppText>
          <AppText style={[styles.axisLabel, styles.axisLabelLow, { top: minY - 7 }]}>{Math.round(minValue)}</AppText>
        </>
      ) : null}
      <View style={styles.labelRow}>
        {points.map((point) => (
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
  };
}

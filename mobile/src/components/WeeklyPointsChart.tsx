import React, { useState } from 'react';
import { LayoutChangeEvent, Text, View } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';

import type { WeeklyStatPoint } from '../lib/api';
import { colors, spacing, typography } from '../theme';

const HEIGHT = 140;
const TOP_PAD = 16;
const BOTTOM_PAD = 22;
const SIDE_PAD = 8;

function buildPath(points: Array<{ x: number; y: number }>): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
}

/** A player's fantasy points across the weeks of one season — Player
 * Detail's "is this guy trending up or down" chart, requested alongside the
 * snap% bar since neither existed before (the season card only ever showed
 * one aggregate PPG number). */
export default function WeeklyPointsChart({ weeks }: { weeks: WeeklyStatPoint[] }) {
  const [width, setWidth] = useState(0);

  const played = weeks.filter((week) => week.fantasy_points_ppr != null);
  if (played.length === 0) {
    return <Text style={styles.empty}>No weekly points recorded for this season yet.</Text>;
  }

  const values = played.map((week) => week.fantasy_points_ppr as number);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = maxValue - minValue || 1;
  const plotWidth = Math.max(width - SIDE_PAD * 2, 1);
  const plotHeight = HEIGHT - TOP_PAD - BOTTOM_PAD;
  const step = played.length > 1 ? plotWidth / (played.length - 1) : 0;

  const points = played.map((week, index) => ({
    x: SIDE_PAD + (played.length > 1 ? step * index : plotWidth / 2),
    y: TOP_PAD + plotHeight - ((week.fantasy_points_ppr as number) - minValue) / range * plotHeight,
    week: week.week,
    value: week.fantasy_points_ppr as number,
  }));

  const onLayout = (event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width);

  return (
    <View onLayout={onLayout}>
      {width > 0 ? (
        <Svg width={width} height={HEIGHT}>
          <Line
            x1={SIDE_PAD}
            y1={TOP_PAD + plotHeight}
            x2={width - SIDE_PAD}
            y2={TOP_PAD + plotHeight}
            stroke={colors.border}
            strokeWidth={1}
          />
          <Path d={buildPath(points)} stroke={colors.accent} strokeWidth={2} fill="none" />
          {points.map((point) => (
            <Circle key={point.week} cx={point.x} cy={point.y} r={3.5} fill={colors.accent} />
          ))}
        </Svg>
      ) : null}
      <View style={styles.labelRow}>
        {points.map((point) => (
          <Text key={point.week} style={styles.weekLabel}>
            {point.week}
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = {
  empty: {
    ...typography.bodyMuted,
    color: colors.textSecondary,
    textAlign: 'center' as const,
    paddingVertical: spacing.lg,
  },
  labelRow: {
    flexDirection: 'row' as const,
    justifyContent: 'space-between' as const,
    marginTop: spacing.xs,
    paddingHorizontal: SIDE_PAD,
  },
  weekLabel: {
    ...typography.caption,
    color: colors.textTertiary,
  },
};

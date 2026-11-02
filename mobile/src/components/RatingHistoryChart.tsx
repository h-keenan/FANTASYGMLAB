import React, { useMemo, useState } from 'react';
import { LayoutChangeEvent, Pressable, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

import AppText from './AppText';
import type { RatingHistoryPoint } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { shortDate } from '../lib/valueHistoryPresentation';
import { spacing, typography, type ThemeColors } from '../theme';

const HEIGHT = 140;
const TOP_PAD = 14;
const BOTTOM_PAD = 8;
const SIDE_PAD = 8;
const LEFT_PAD = 30;
const GRADIENT_ID = 'ratingHistoryFill';

const path = (pts: Array<{ x: number; y: number }>) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

/** Overall rating (0-99) over the real stored daily snapshots; same drawing
 * language as WeeklyPointsChart. Tap a point for its date and value. */
export default function RatingHistoryChart({ points }: { points: RatingHistoryPoint[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [width, setWidth] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  if (points.length < 2) return null;

  const values = points.map((p) => p.rating);
  const lo = Math.max(0, Math.min(...values) - 3);
  const hi = Math.min(99, Math.max(...values) + 3);
  const range = hi - lo || 1;
  const plotW = Math.max(width - LEFT_PAD - SIDE_PAD, 1);
  const plotH = HEIGHT - TOP_PAD - BOTTOM_PAD;
  const step = plotW / (points.length - 1);
  const pts = points.map((p, i) => ({
    x: LEFT_PAD + step * i,
    y: TOP_PAD + plotH - ((p.rating - lo) / range) * plotH,
    date: p.date,
    rating: p.rating,
  }));
  const baseY = TOP_PAD + plotH;
  const area = `${path(pts)} L ${pts[pts.length - 1].x} ${baseY} L ${pts[0].x} ${baseY} Z`;
  const showDots = points.length <= 30;
  const sel = selected != null ? pts[selected] : null;

  return (
    <View onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)} testID="rating-history-chart">
      {width > 0 ? (
        <Svg width={width} height={HEIGHT}>
          <Defs>
            <LinearGradient id={GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.accent} stopOpacity={0.35} />
              <Stop offset="1" stopColor={colors.accent} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Line x1={LEFT_PAD} y1={baseY} x2={width - SIDE_PAD} y2={baseY} stroke={colors.border} strokeWidth={1} />
          <Path d={area} fill={`url(#${GRADIENT_ID})`} />
          <Path d={path(pts)} stroke={colors.accent} strokeWidth={2} fill="none" />
          {showDots
            ? pts.map((p, i) => (
                <Circle key={p.date} cx={p.x} cy={p.y} r={i === selected ? 5.5 : 3.5} fill={colors.accent} />
              ))
            : null}
        </Svg>
      ) : null}
      {width > 0
        ? pts.map((p, i) => (
            <Pressable
              key={p.date}
              onPress={() => setSelected((c) => (c === i ? null : i))}
              hitSlop={showDots ? 10 : 0}
              style={[styles.touch, { left: p.x - (showDots ? 14 : Math.max(step / 2, 4)), top: 0, width: showDots ? 28 : Math.max(step, 8), height: HEIGHT }]}
            />
          ))
        : null}
      {sel ? (
        <View pointerEvents="none" style={[styles.tooltip, { left: Math.min(Math.max(sel.x - 50, 0), Math.max(width - 100, 0)), top: Math.max(sel.y - 34, 0) }]}>
          <AppText style={styles.tooltipText}>
            {shortDate(sel.date)} · {sel.rating}
          </AppText>
        </View>
      ) : null}
      {width > 0 ? (
        <>
          <AppText style={[styles.axis, { top: TOP_PAD - 7 }]}>{Math.round(hi)}</AppText>
          <AppText style={[styles.axis, { top: baseY - 7 }]}>{Math.round(lo)}</AppText>
        </>
      ) : null}
      <View style={styles.dates}>
        <AppText style={styles.dateText}>{shortDate(points[0].date)}</AppText>
        <AppText style={styles.dateText}>{shortDate(points[points.length - 1].date)}</AppText>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return {
    touch: { position: 'absolute' as const },
    tooltip: {
      position: 'absolute' as const,
      width: 100,
      paddingVertical: 4,
      borderRadius: 6,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
      alignItems: 'center' as const,
    },
    tooltipText: { ...typography.caption, color: colors.textPrimary, fontWeight: '700' as const },
    axis: { ...typography.caption, position: 'absolute' as const, left: 0, width: LEFT_PAD - 4, textAlign: 'right' as const, color: colors.textTertiary },
    dates: { flexDirection: 'row' as const, justifyContent: 'space-between' as const, paddingLeft: LEFT_PAD, paddingRight: SIDE_PAD, marginTop: spacing.xs },
    dateText: { ...typography.caption, color: colors.textTertiary },
  };
}

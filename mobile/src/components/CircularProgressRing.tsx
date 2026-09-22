import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';
import Svg, { Circle } from 'react-native-svg';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

/** A confidence/value ring instead of a linear bar — pulled directly from a
 * UI reference coridian_ shared (the same circular-percentage pattern
 * showed up independently in an earlier brand-sheet reference too), used
 * where one number is the headline of a section rather than one of several
 * inline stats. */
export default function CircularProgressRing({
  percent,
  size = 72,
  strokeWidth = 7,
  color,
  label,
  valueLabel,
  valueFontScale = 0.26,
}: {
  /** 0-100 */
  percent: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  /** Small caption under the number, e.g. "CONFIDENCE" */
  label?: string;
  /** Overrides the centered "N%" text — e.g. "HIGH" */
  valueLabel?: string;
  /** Centered text size as a fraction of `size`. The default is tuned for a
   * three-character "87%"; a short plain number (a 0-99 rating) can carry a
   * bigger scale without crowding the stroke. */
  valueFontScale?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const resolvedColor = color ?? colors.accent;
  const clamped = Math.max(0, Math.min(100, percent));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - clamped / 100);
  const center = size / 2;

  return (
    <View style={styles.wrap}>
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size}>
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={colors.border}
            strokeWidth={strokeWidth}
            fill="none"
          />
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={resolvedColor}
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={`${circumference} ${circumference}`}
            strokeDashoffset={dashOffset}
            // Start at 12 o'clock, not 3 o'clock (SVG circles default to 0deg = right).
            rotation={-90}
            originX={center}
            originY={center}
          />
        </Svg>
        <View style={[StyleSheet.absoluteFillObject, styles.centerContent]}>
          <AppText style={[styles.value, { color: resolvedColor, fontSize: size * valueFontScale }]} numberOfLines={1}>
            {valueLabel ?? `${Math.round(clamped)}%`}
          </AppText>
        </View>
      </View>
      {label ? <AppText style={styles.label}>{label}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { alignItems: 'center' },
    centerContent: { alignItems: 'center', justifyContent: 'center' },
    value: { fontWeight: '800' },
    label: {
      fontSize: 10,
      fontWeight: '700',
      color: colors.textTertiary,
      letterSpacing: 0.5,
      textTransform: 'uppercase',
      marginTop: 4,
    },
  });
}

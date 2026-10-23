import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { radii, spacing } from '../theme';

/**
 * The one status badge: small uppercase rounded pill tinted 15% from one
 * semantic color. Mirrors web-next's ToneBadge. Position badges are the one
 * exception and keep `PositionBadge`.
 */
export default function ToneBadge({
  label,
  color,
  size = 'sm',
  icon,
  solid,
  textColor,
  style,
}: {
  label: string;
  color: string;
  /** `xs` is the dense in-row pill (tier, usage trend, NEW). */
  size?: 'sm' | 'xs';
  icon?: keyof typeof Ionicons.glyphMap;
  /** Filled with `color` instead of a 15% tint (used by NEW); pass `textColor`. */
  solid?: boolean;
  textColor?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const fg = textColor ?? color;
  return (
    <View
      style={[
        styles.pill,
        size === 'xs' && styles.pillXs,
        { backgroundColor: solid ? color : withAlpha(color, 0.15) },
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={9} color={fg} /> : null}
      <AppText style={[styles.text, size === 'xs' && styles.textXs, { color: fg }]} numberOfLines={1}>
        {label}
      </AppText>
    </View>
  );
}

/** '#rrggbb' or 'rgb(a)' -> rgba with the given alpha; other strings pass through. */
export function withAlpha(color: string, alpha: number): string {
  const hex = /^#([0-9a-f]{6})$/i.exec(color);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
  }
  const rgb = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(color);
  if (rgb) return `rgba(${rgb[1]},${rgb[2]},${rgb[3]},${alpha})`;
  return color;
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm - 2,
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },
  pillXs: { paddingHorizontal: spacing.xs + 2, paddingVertical: 1 },
  text: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6 },
  textXs: { fontSize: 9, letterSpacing: 0.4 },
});

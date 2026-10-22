import React from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { radii, spacing } from '../theme';

/**
 * The one status badge: small uppercase rounded pill tinted 15% from one
 * semantic color. Mirrors web-next's ToneBadge. Position badges are the one
 * exception and keep `PositionBadge`.
 */
export default function ToneBadge({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: withAlpha(color, 0.15) }]}>
      <AppText style={[styles.text, { color }]} numberOfLines={1}>
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
  pill: { borderRadius: radii.pill, paddingHorizontal: spacing.sm - 2, paddingVertical: 2, alignSelf: 'flex-start' },
  text: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6 },
});

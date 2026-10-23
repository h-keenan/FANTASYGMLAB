import React from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { positionBadgeColors, positionBadgeLabel, radii } from '../theme';

/** The single shared position pill (owner decision 2026-10-22, option A).
 * Fully rounded, tinted by a fixed semantic color per position, tight
 * uppercase tracking, min-width so 1-3 letter positions share a width feel.
 * Mirrors web-next's PositionBadge (`.position-badge*` in globals.css) and
 * the share-card SharePositionBadge: same sizes (sm 11/20, md 13/24), same
 * 14% fill / 45% border / 70% hue text recipe. `rank` appends a position
 * rank ("RB12"); `label` overrides the text (e.g. a numbered slot). */
export default function PositionBadge({
  position,
  size = 'sm',
  rank,
  label,
}: {
  position: string | null | undefined;
  size?: 'sm' | 'md';
  rank?: number | string | null;
  label?: string;
}) {
  const { isDark, colors } = useThemeMode();
  if (!position) return null;
  const tint = positionBadgeColors(position, isDark, colors.textPrimary, colors.textSecondary);
  const text = `${label ?? positionBadgeLabel(position)}${rank != null && rank !== '' ? rank : ''}`;
  return (
    <View
      style={[
        styles.badge,
        size === 'md' && styles.badgeMd,
        { backgroundColor: tint.fill, borderColor: tint.border },
      ]}
    >
      <AppText style={[styles.text, size === 'md' && styles.textMd, { color: tint.text }]} numberOfLines={1}>
        {text}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.pill,
    borderWidth: 1,
    height: 20,
    minWidth: 32,
    paddingHorizontal: 8,
  },
  badgeMd: { height: 24, minWidth: 38, paddingHorizontal: 10 },
  text: { fontSize: 11, fontWeight: '800', letterSpacing: 0.44, textTransform: 'uppercase' },
  textMd: { fontSize: 13, letterSpacing: 0.52 },
});

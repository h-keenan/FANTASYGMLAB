import React from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing } from '../theme';

/**
 * Small "94 OVR" pill — the 0-99 headline rating (see
 * modules.player_quick_view._overall_rating_from_percentile) shown as a
 * secondary badge next to a row's primary raw value_score, never in place
 * of it. Same tinted-chip visual language as PositionBadge/TierBadge, but
 * intentionally neutral/quiet: this is a supporting number, not the row's
 * headline value.
 *
 * Renders nothing for `null`/`undefined` — the same "too thin a pool to
 * rank against" contract every overall_rating field already carries, so a
 * screen never has to gate on presence itself.
 */
export default function OverallRatingBadge({
  rating,
  size = 'sm',
}: {
  rating: number | null | undefined;
  size?: 'sm' | 'md';
}) {
  const { colors } = useThemeMode();
  if (rating === null || rating === undefined || !Number.isFinite(rating)) return null;
  return (
    <View
      style={[
        styles.badge,
        size === 'md' && styles.badgeMd,
        { backgroundColor: `${colors.textSecondary}1f`, borderColor: `${colors.textSecondary}59` },
      ]}
    >
      <AppText style={[styles.text, size === 'md' && styles.textMd, { color: colors.textSecondary }]} numberOfLines={1}>
        {Math.round(rating)} OVR
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    // No alignSelf override: every call site places this inside a column
    // whose own alignItems (flex-end next to a right-aligned value score,
    // or center in a centered card) is what should decide the pill's
    // horizontal position — unlike PositionBadge/TierBadge, which always
    // sit inside a row and need flex-start to avoid stretching to the
    // row's full height.
    flexShrink: 0,
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  badgeMd: { paddingHorizontal: spacing.sm, paddingVertical: 3 },
  text: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  textMd: { fontSize: 11 },
});

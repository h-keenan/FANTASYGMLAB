import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { positionColor, radii, spacing } from '../theme';

/** Colored position chip — QB/RB/WR/TE/K/DEF each get web's exact
 * position-identity color (modules/design_tokens.py's --color-position-*
 * tokens) instead of plain text. Same tinted-chip visual language as
 * TierBadge. */
export default function PositionBadge({
  position,
  size = 'sm',
}: {
  position: string | null | undefined;
  size?: 'sm' | 'md';
}) {
  if (!position) return null;
  const color = positionColor(position);
  return (
    <View
      style={[
        styles.badge,
        size === 'md' && styles.badgeMd,
        { backgroundColor: `${color}26`, borderColor: `${color}80` },
      ]}
    >
      <Text style={[styles.text, size === 'md' && styles.textMd, { color }]} numberOfLines={1}>
        {position.toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  badgeMd: { paddingHorizontal: spacing.sm, paddingVertical: 3 },
  text: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  textMd: { fontSize: 11 },
});

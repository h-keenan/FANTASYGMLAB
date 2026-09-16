import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { resolvePlayerTier } from '../lib/playerTier';
import { radii, spacing } from '../theme';

export default function TierBadge({
  storedTier,
  size = 'sm',
}: {
  storedTier: string | null | undefined;
  size?: 'sm' | 'md';
}) {
  if (!storedTier) return null;
  const tier = resolvePlayerTier(storedTier);
  const label = size === 'md' ? tier.shortLabel : tier.abbrLabel;
  return (
    <View
      style={[
        styles.badge,
        size === 'md' && styles.badgeMd,
        { backgroundColor: `${tier.color}26`, borderColor: `${tier.color}80` },
      ]}
    >
      <Text style={[styles.text, size === 'md' && styles.textMd, { color: tier.color }]} numberOfLines={1}>
        {label}
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

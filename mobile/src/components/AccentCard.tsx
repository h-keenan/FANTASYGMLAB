import React from 'react';
import { StyleProp, StyleSheet, ViewStyle } from 'react-native';

import AnimatedCard from './AnimatedCard';
import { spacing } from '../theme';

/**
 * The one accent-left-edge card: a card with a 3pt left rail in a semantic
 * color and the same padding everywhere (mirrors web-next's AccentCard).
 */
export default function AccentCard({
  accent,
  compact = false,
  style,
  children,
}: {
  accent: string;
  compact?: boolean;
  style?: StyleProp<ViewStyle>;
  children: React.ReactNode;
}) {
  return (
    <AnimatedCard
      style={StyleSheet.flatten([
        { borderLeftWidth: 3, borderLeftColor: accent, padding: compact ? spacing.md : spacing.lg },
        styles.gap,
        style,
      ])}
    >
      {children}
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({ gap: { gap: spacing.sm } });

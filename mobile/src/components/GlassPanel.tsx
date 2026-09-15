import React from 'react';
import { Platform, StyleSheet, View, type ViewStyle } from 'react-native';
import { BlurView } from 'expo-blur';

import { colors, radii } from '../theme';

interface GlassPanelProps {
  style?: ViewStyle | ViewStyle[];
  children: React.ReactNode;
}

/**
 * A translucent "glass" surface for one-off hero/header treatments (not
 * list rows — a live blur per scrolling row is expensive, so AnimatedCard
 * uses a flat tinted surface instead). iOS gets a real blur; Android falls
 * back to a tinted solid, since Android's blur renderer is heavier and less
 * consistent across devices.
 */
export default function GlassPanel({ style, children }: GlassPanelProps) {
  if (Platform.OS === 'ios') {
    return (
      <BlurView intensity={40} tint="dark" style={[styles.panel, style]}>
        {children}
      </BlurView>
    );
  }
  return <View style={[styles.panel, styles.androidFallback, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.borderStrong,
    overflow: 'hidden',
  },
  androidFallback: {
    backgroundColor: colors.backgroundElevated,
  },
});

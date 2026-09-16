import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { colors, radii, spacing } from '../theme';

/**
 * Branded launch/loading state, matching the web app's splash (FGL mark,
 * "FOUNDER BETA" badge, a short status line) rather than a bare spinner.
 */
export default function LoadingScreen({ status = 'Loading…' }: { status?: string }) {
  return (
    <View style={styles.container}>
      <Image source={require('../../assets/icon.png')} style={styles.mark} />
      <Text style={styles.title}>FantasyGM Lab</Text>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>FOUNDER BETA</Text>
      </View>
      <Text style={styles.status}>{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.sm,
  },
  mark: { width: 72, height: 72, borderRadius: radii.md, marginBottom: spacing.md },
  title: { fontSize: 22, fontWeight: '700', color: colors.textPrimary },
  badge: {
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    marginTop: spacing.xs,
  },
  badgeText: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
  status: { fontSize: 14, color: colors.textSecondary, marginTop: spacing.lg },
});

import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * "Week N League Recap is ready / Tap to see this week's storylines" card —
 * originally AlertsScreen-only (coridian_'s brief), now shared so Dashboard
 * can render the exact same proven pattern for its own "new, unopened
 * recap" module instead of inventing a second visual language for the same
 * idea (Magna Carta §44: shared component first). AlertsScreen's own
 * rendering is unchanged — same AnimatedCard+IconCircle+chevron shape, same
 * styles, just extracted here so both call sites stay byte-for-byte
 * identical in appearance.
 */
export default function RecapReadyCard({ week, onPress }: { week: number; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity onPress={onPress}>
      <AnimatedCard glow style={styles.recapCard}>
        <IconCircle name="newspaper-outline" color={colors.accent} size={36} style={styles.recapIconDisc} />
        <View style={styles.recapTextGroup}>
          <AppText style={styles.recapTitle}>Week {week} League Recap is ready</AppText>
          <AppText style={styles.recapSubtitle}>Tap to see this week's storylines</AppText>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
      </AnimatedCard>
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    recapCard: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: spacing.md,
      marginBottom: spacing.md,
    },
    recapIconDisc: { marginRight: spacing.sm },
    recapTextGroup: { flex: 1 },
    recapTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    recapSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  });
}

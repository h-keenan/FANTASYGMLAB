import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import PremiumGlow from '../components/PremiumGlow';
import GridBackground from '../components/GridBackground';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TrialLapsed'>;

/**
 * One-time interstitial shown right after a free trial expires without
 * converting — greets the lapsed-trial moment directly instead of letting
 * someone just quietly hit individual feature locks one at a time (Zach,
 * 2026-10-16: "if they lapsed the trial we need a page to show them the new
 * deal"). Shown at most once per lapse — see lib/trialLapsedSeen.ts.
 *
 * Deliberately thin: the actual plans/pricing/purchase flow is Paywall's
 * job (one real purchase surface, not two), this screen is just the
 * greeting + the door into it.
 */
export default function TrialLapsedScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  return (
    <View style={styles.root}>
      <GridBackground />
      <View style={[styles.content, { paddingTop: headerHeight, paddingBottom: orbClearance }]}>
        <TouchableOpacity style={styles.closeButton} onPress={() => navigation.goBack()} hitSlop={8}>
          <AppText style={styles.closeButtonText}>Not now</AppText>
        </TouchableOpacity>

        <View style={styles.body}>
          <Ionicons name="time-outline" size={48} color={colors.premium} style={styles.icon} />
          <AppText style={styles.title}>Your free trial has ended</AppText>
          <AppText style={styles.subtitle}>
            Here's the new Pro pricing — take a look before you decide.
          </AppText>
        </View>

        <PremiumGlow radius={radii.md} style={styles.glowWrap}>
          <TouchableOpacity style={styles.primaryButton} onPress={() => navigation.replace('Paywall')}>
            <AppText style={styles.primaryButtonText}>See the new plans</AppText>
          </TouchableOpacity>
        </PremiumGlow>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    content: { flex: 1, paddingHorizontal: spacing.lg, justifyContent: 'space-between' },
    closeButton: { alignSelf: 'flex-end', paddingVertical: spacing.sm },
    closeButtonText: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
    body: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
    icon: { marginBottom: spacing.sm },
    title: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, textAlign: 'center' },
    subtitle: {
      fontSize: 15,
      color: colors.textSecondary,
      textAlign: 'center',
      lineHeight: 21,
      paddingHorizontal: spacing.md,
    },
    primaryButton: {
      backgroundColor: colors.premiumFill,
      borderRadius: radii.md,
      paddingVertical: spacing.md + 2,
      alignItems: 'center',
    },
    glowWrap: { marginBottom: spacing.lg },
    primaryButtonText: { fontSize: 16, fontWeight: '600', color: colors.onPremium },
  });
}

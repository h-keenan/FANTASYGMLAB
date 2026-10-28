import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { trackUse } from '../lib/analytics';
import type { LimitWallModel } from '../lib/limitWall';
import AccentCard from './AccentCard';
import PremiumGlow from './PremiumGlow';
import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * The wall a plan limit shows instead of a generic error: what limit, when it
 * resets, what Pro adds, one CTA to Paywall (which shows guests the account
 * step first). Model comes from lib/limitWall.ts, shared with web-next's
 * LimitWall.
 */
export default function LimitWall({ wall, feature }: { wall: LimitWallModel; feature: string }) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  useEffect(() => {
    trackUse(feature, 'gate_seen', { tier: 'free' });
  }, [feature]);

  return (
    <PremiumGlow radius={radii.md} pulse={false} strength={0.6}>
      <AccentCard accent={colors.premium} style={styles.card}>
        <View style={styles.titleRow}>
          <Ionicons name="lock-closed" size={16} color={colors.premium} />
          <AppText style={styles.title} accessibilityRole="alert">
            {wall.title}
          </AppText>
        </View>
        <AppText style={styles.body}>{wall.body}</AppText>
        <AppText style={styles.pro}>{wall.proLine}</AppText>
        <Button
          label={wall.ctaLabel}
          variant="premium"
          onPress={() => {
            trackUse(feature, 'upsell_tapped', { tier: 'free' });
            navigation.navigate('Paywall');
          }}
          style={styles.button}
        />
      </AccentCard>
    </PremiumGlow>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { borderWidth: 1, borderColor: colors.premium },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    body: { fontSize: 12, color: colors.textPrimary, lineHeight: 16 },
    pro: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    button: { alignSelf: 'flex-start' },
  });
}

import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { trackUse } from '../lib/analytics';
import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

interface Props {
  title: string;
  description: string;
  /** Stable analytics id of the gated feature (defaults to a slug of title). */
  feature?: string;
}

/**
 * The locked card shown wherever a Free account has content withheld
 * server-side: the shared AccentCard (premium edge) with the upsell copy and
 * a primary Upgrade button that goes straight to Paywall. Mirrors web-next's
 * PremiumUpsellCard.
 */
export default function PremiumLock({ title, description, feature }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Conversion-by-feature: locked card seen / upsell tapped (same events as web).
  const gateFeature =
    feature ?? (title.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'premium');
  useEffect(() => {
    trackUse(gateFeature, 'gate_seen', { tier: 'free' });
  }, [gateFeature]);

  return (
    <AccentCard accent={colors.premium}>
      <View style={styles.titleRow}>
        <Ionicons name="lock-closed" size={16} color={colors.premium} />
        <AppText style={styles.title}>{title}</AppText>
      </View>
      <AppText style={styles.description}>{description}</AppText>
      <Button
        label="Upgrade"
        onPress={() => {
          trackUse(gateFeature, 'upsell_tapped', { tier: 'free' });
          navigation.navigate('Paywall');
        }}
        style={styles.button}
      />
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    description: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    button: { alignSelf: 'flex-start' },
  });
}

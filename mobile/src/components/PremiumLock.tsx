import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { trackUse } from '../lib/analytics';
import { paidPreview } from '../lib/paidPreviews';
import AccentCard from './AccentCard';
import PremiumGlow from './PremiumGlow';
import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

interface Props {
  title: string;
  description: string;
  /** Stable analytics id of the gated feature (defaults to a slug of title). */
  feature?: string;
  /** Key into lib/paidPreviews when it differs from `feature` (e.g. games_what_if -> what_if). */
  previewKey?: string;
  /** Names the person's own league in the preview bullets. */
  leagueName?: string;
  /** One real fact about the person's own league the screen already has (never invented). */
  example?: string;
}

/**
 * The locked card shown wherever a Free account has content withheld
 * server-side: the shared AccentCard (premium edge) with the upsell copy and
 * a primary Upgrade button that goes straight to Paywall. Mirrors web-next's
 * PremiumUpsellCard.
 */
export default function PremiumLock({ title, description, feature, previewKey, leagueName, example }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Conversion-by-feature: locked card seen / upsell tapped (same events as web).
  const gateFeature =
    feature ?? (title.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'premium');
  useEffect(() => {
    trackUse(gateFeature, 'gate_seen', { tier: 'free' });
  }, [gateFeature]);

  const preview = paidPreview(previewKey ?? gateFeature, leagueName);

  return (
    <PremiumGlow radius={radii.md} pulse={false} strength={0.6}>
    <AccentCard accent={colors.premium} style={styles.card}>
      <View style={styles.titleRow}>
        <Ionicons name="lock-closed" size={16} color={colors.premium} />
        <AppText style={styles.title}>{title}</AppText>
      </View>
      <AppText style={styles.description}>{description}</AppText>
      {preview ? (
        <View style={styles.preview} testID="paid-preview">
          <AppText style={styles.previewLabel}>WHAT YOU GET WITH PRO</AppText>
          {preview.bullets.map((bullet) => (
            <View key={bullet} style={styles.bulletRow}>
              <AppText style={styles.bulletDot}>{'\u2022'}</AppText>
              <AppText style={styles.bulletText}>{bullet}</AppText>
            </View>
          ))}
          {example ? <AppText style={styles.example}>{example}</AppText> : null}
          {preview.freeIncludes ? <AppText style={styles.freeIncludes}>{preview.freeIncludes}</AppText> : null}
        </View>
      ) : null}
      <Button
        label="Upgrade"
        variant="premium"
        onPress={() => {
          trackUse(gateFeature, 'upsell_tapped', { tier: 'free' });
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
    title: { flex: 1, fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    description: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 18 },
    button: { alignSelf: 'flex-start' },
    preview: { gap: 4 },
    previewLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    bulletRow: { flexDirection: 'row', gap: spacing.sm },
    bulletDot: { fontSize: 13.5, lineHeight: 18, color: colors.textSecondary },
    bulletText: { flex: 1, fontSize: 13.5, lineHeight: 18, color: colors.textPrimary },
    example: { fontSize: 13.5, lineHeight: 18, fontWeight: '700', color: colors.textPrimary },
    freeIncludes: { fontSize: 12.5, lineHeight: 17, color: colors.textTertiary },
  });
}

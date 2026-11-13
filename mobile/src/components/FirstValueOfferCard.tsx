import React, { useEffect, useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { trackUse } from '../lib/analytics';
import {
  TRIAL_OFFER_CTA,
  TRIAL_OFFER_DISMISS,
  TRIAL_OFFER_NOTE,
  TRIAL_OFFER_TITLE,
  funnelStepIndex,
  shouldShowTrialOffer,
} from '../lib/firstRunFlow';
import { trackOnboardingStepViewed } from '../lib/onboardingAnalytics';
import { PAYWALL_HERO_SUB } from '../lib/paywallCopy';
import { LINK_HIT_SLOP, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';

const SURFACE = 'first_league_today';

/**
 * The trial offer, moved after connect (owner decision 2026-11): a quiet,
 * dismissible card UNDER the first league's Today briefing, shown once. It is
 * not a screen and gates nothing. Price and trial terms live on the Paywall
 * screen (real store data), never on this card. Web twin:
 * web-next/src/components/FirstValueOfferCard.tsx.
 */
export default function FirstValueOfferCard({ isPremium }: { isPremium: boolean }) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { trialOfferArmed, resolveTrialOffer } = useOnboarding();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const visible = shouldShowTrialOffer({ state: trialOfferArmed ? 'armed' : 'idle', isPremium, onLeagueHome: true });

  useEffect(() => {
    // Funnel: the first league view was reached (armed at first run only, so
    // returning users never count).
    if (trialOfferArmed) trackOnboardingStepViewed('first_league_view', funnelStepIndex('first_league_view'));
  }, [trialOfferArmed]);
  useEffect(() => {
    if (visible) trackUse('paywall', 'offer_seen', { tier: 'free', props: { source_surface: SURFACE } });
  }, [visible]);

  if (!visible) return null;

  return (
    <AccentCard accent={colors.premium} style={styles.card}>
      <AppText style={styles.title}>{TRIAL_OFFER_TITLE}</AppText>
      <AppText style={styles.body}>{PAYWALL_HERO_SUB}</AppText>
      <AppText style={styles.note}>{TRIAL_OFFER_NOTE}</AppText>
      <View style={styles.actions}>
        <Button
          label={TRIAL_OFFER_CTA}
          variant="premium"
          onPress={() => {
            trackUse('paywall', 'offer_cta', { tier: 'free', props: { source_surface: SURFACE } });
            resolveTrialOffer();
            navigation.navigate('Paywall');
          }}
        />
        <TouchableOpacity
          accessibilityRole="button"
          onPress={() => {
            trackUse('paywall', 'offer_dismissed', { tier: 'free', props: { source_surface: SURFACE } });
            resolveTrialOffer();
          }}
          hitSlop={LINK_HIT_SLOP}
        >
          <AppText style={styles.dismiss}>{TRIAL_OFFER_DISMISS}</AppText>
        </TouchableOpacity>
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { gap: spacing.sm },
    title: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    body: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 18 },
    note: { fontSize: 12.5, color: colors.textTertiary, lineHeight: 17 },
    actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg, flexWrap: 'wrap' },
    dismiss: { fontSize: 14, fontWeight: '600', color: colors.textSecondary, textDecorationLine: 'underline' },
  });
}

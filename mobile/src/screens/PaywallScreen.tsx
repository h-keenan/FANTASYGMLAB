import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { PurchasesOffering, PurchasesPackage } from 'react-native-purchases';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import { useOrbClearance } from '../lib/orbLayout';
import {
  getCurrentOffering,
  purchasePackage,
  restorePurchases,
} from '../lib/revenuecat';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Paywall'>;

// Every line here corresponds to a real, server-enforced gate — see the
// paywall audit (2026-09-18). Don't add a benefit unless something in
// services/mobile_api_service.py actually withholds it from a Free account.
const FEATURES = [
  'Your full Next Move briefing, not just the top 4',
  'Full League Pulse — see the whole league’s contenders and rebuilders',
  'The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist',
  'Every Trade Hub idea, not just the first 2 (skip the ads)',
  'GM Targets watchlist up to 50 players (Free is capped at 3)',
];

export default function PaywallScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [offering, setOffering] = useState<PurchasesOffering | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [purchasing, setPurchasing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [purchased, setPurchased] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const current = await getCurrentOffering();
        if (cancelled) return;
        setOffering(current);
        const preferred =
          current?.availablePackages.find((p) => p.identifier === 'annual') ??
          current?.availablePackages[0] ??
          null;
        setSelectedId(preferred?.identifier ?? null);
      } catch {
        if (!cancelled) setLoadError('Could not load subscription options. Pull down to retry.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const packages = offering?.availablePackages ?? [];
  const selected = packages.find((p) => p.identifier === selectedId) ?? null;

  const onPurchase = async (pack: PurchasesPackage) => {
    setPurchaseError(null);
    setPurchasing(true);
    const outcome = await purchasePackage(pack);
    setPurchasing(false);
    if (outcome.purchased) {
      setPurchased(true);
      return;
    }
    if (outcome.cancelled) return;
    setPurchaseError(outcome.errorMessage ?? 'Purchase failed. Please try again.');
  };

  const onRestore = async () => {
    setPurchaseError(null);
    setRestoring(true);
    const active = await restorePurchases();
    setRestoring(false);
    if (active) {
      setPurchased(true);
    } else {
      setPurchaseError('No active purchase found for this account.');
    }
  };

  if (purchased) {
    return (
      <View style={styles.center}>
        <AppText style={styles.successTitle}>You're on Premium</AppText>
        <AppText style={styles.successSubtitle}>
          It may take a moment to reflect everywhere in the app.
        </AppText>
        <TouchableOpacity style={styles.primaryButton} onPress={() => navigation.goBack()}>
          <AppText style={styles.primaryButtonText}>Done</AppText>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.root}>
    <GridBackground />
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}
      showsVerticalScrollIndicator={false}
    >
      <TouchableOpacity style={styles.closeButton} onPress={() => navigation.goBack()} hitSlop={8}>
        <AppText style={styles.closeButtonText}>Close</AppText>
      </TouchableOpacity>

      <AppText style={styles.title}>FantasyGM Lab Premium</AppText>
      <AppText style={styles.subtitle}>Founder Beta pricing — locked in for as long as you stay subscribed.</AppText>

      <View style={styles.features}>
        {FEATURES.map((feature) => (
          <View key={feature} style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color={colors.success} style={styles.featureIcon} />
            <AppText style={styles.featureText}>{feature}</AppText>
          </View>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator style={styles.loadingIndicator} color={colors.accent} />
      ) : loadError ? (
        <AppText style={styles.error}>{loadError}</AppText>
      ) : packages.length === 0 ? (
        <AppText style={styles.error}>No subscription plans are available right now.</AppText>
      ) : (
        <View style={styles.packages}>
          {packages.map((pack) => {
            const isSelected = pack.identifier === selectedId;
            const isAnnual = pack.identifier === 'annual';
            return (
              <AnimatedCard
                key={pack.identifier}
                style={StyleSheet.flatten([
                  styles.packageCard,
                  isSelected && styles.packageCardSelected,
                ])}
                onPress={() => setSelectedId(pack.identifier)}
              >
                <View style={styles.packageRow}>
                  <View style={styles.packageLabelGroup}>
                    <AppText style={styles.packageTitle}>{pack.product.title || pack.identifier}</AppText>
                    {isAnnual ? (
                      <View style={styles.bestValueBadge}>
                        <AppText style={styles.bestValueBadgeText}>Best value</AppText>
                      </View>
                    ) : null}
                  </View>
                  <AppText style={styles.packagePrice}>{pack.product.priceString}</AppText>
                </View>
              </AnimatedCard>
            );
          })}
        </View>
      )}

      {purchaseError ? <AppText style={styles.error}>{purchaseError}</AppText> : null}

      <TouchableOpacity
        style={[styles.primaryButton, (!selected || purchasing) && styles.primaryButtonDisabled]}
        onPress={() => selected && onPurchase(selected)}
        disabled={!selected || purchasing}
      >
        {purchasing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <AppText style={styles.primaryButtonText}>Continue</AppText>
        )}
      </TouchableOpacity>

      <TouchableOpacity onPress={onRestore} disabled={restoring} style={styles.restoreButton}>
        <AppText style={styles.restoreButtonText}>
          {restoring ? 'Restoring…' : 'Restore purchases'}
        </AppText>
      </TouchableOpacity>

      <AppText style={styles.disclosure}>
        Payment is charged to your account at confirmation of purchase. Your subscription
        automatically renews unless auto-renew is turned off at least 24 hours before the end of
        the current period. Manage or cancel anytime in your device's account settings. By
        continuing, you agree to our{' '}
        <AppText style={styles.disclosureLink} onPress={() => navigation.navigate('LegalPage', { pageKey: 'terms' })}>
          Terms of Use
        </AppText>{' '}
        and{' '}
        <AppText
          style={styles.disclosureLink}
          onPress={() => navigation.navigate('LegalPage', { pageKey: 'subscription_terms' })}
        >
          Subscription Terms
        </AppText>{' '}
        and{' '}
        <AppText style={styles.disclosureLink} onPress={() => navigation.navigate('LegalPage', { pageKey: 'privacy' })}>
          Privacy Policy
        </AppText>
        .
      </AppText>
    </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  root: { flex: 1 },
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    paddingHorizontal: spacing.xl,
  },
  closeButton: { alignSelf: 'flex-end', marginBottom: spacing.md },
  closeButtonText: { color: colors.textSecondary, fontSize: 15, fontWeight: '500' },
  title: { fontSize: 26, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.xs },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginBottom: spacing.xl, lineHeight: 20 },
  features: { marginBottom: spacing.xl, gap: spacing.sm },
  featureRow: { flexDirection: 'row', alignItems: 'flex-start' },
  featureIcon: { marginRight: spacing.sm, marginTop: 1 },
  featureText: { flex: 1, color: colors.textPrimary, fontSize: 15, lineHeight: 21 },
  loadingIndicator: { marginVertical: spacing.xl },
  packages: { gap: spacing.sm, marginBottom: spacing.lg },
  packageCard: { borderWidth: 2, borderColor: 'transparent' },
  packageCardSelected: { borderColor: colors.accent },
  packageRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  packageLabelGroup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  packageTitle: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  packagePrice: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  bestValueBadge: {
    backgroundColor: colors.premiumMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  bestValueBadgeText: { color: colors.premium, fontSize: 10, fontWeight: '700' },
  primaryButton: {
    backgroundColor: colors.accent,
    borderRadius: radii.md,
    paddingVertical: spacing.md + 2,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  primaryButtonDisabled: { opacity: 0.5 },
  primaryButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  restoreButton: { alignItems: 'center', marginTop: spacing.lg },
  restoreButtonText: { color: colors.accent, fontSize: 14, fontWeight: '500' },
  disclosure: {
    fontSize: 11,
    color: colors.textTertiary,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: spacing.xl,
  },
  disclosureLink: { color: colors.accent, fontWeight: '600' },
  error: { color: colors.danger, marginBottom: spacing.md },
  successTitle: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
  successSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  });
}

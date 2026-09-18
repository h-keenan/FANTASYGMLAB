import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
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
import { colors, radii, spacing } from '../theme';
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
        <Text style={styles.successTitle}>You're on Premium</Text>
        <Text style={styles.successSubtitle}>
          It may take a moment to reflect everywhere in the app.
        </Text>
        <TouchableOpacity style={styles.primaryButton} onPress={() => navigation.goBack()}>
          <Text style={styles.primaryButtonText}>Done</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}
      showsVerticalScrollIndicator={false}
    >
      <TouchableOpacity style={styles.closeButton} onPress={() => navigation.goBack()} hitSlop={8}>
        <Text style={styles.closeButtonText}>Close</Text>
      </TouchableOpacity>

      <Text style={styles.title}>FantasyGM Lab Premium</Text>
      <Text style={styles.subtitle}>Founder Beta pricing — locked in for as long as you stay subscribed.</Text>

      <View style={styles.features}>
        {FEATURES.map((feature) => (
          <View key={feature} style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color={colors.success} style={styles.featureIcon} />
            <Text style={styles.featureText}>{feature}</Text>
          </View>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator style={styles.loadingIndicator} color={colors.accent} />
      ) : loadError ? (
        <Text style={styles.error}>{loadError}</Text>
      ) : packages.length === 0 ? (
        <Text style={styles.error}>No subscription plans are available right now.</Text>
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
                    <Text style={styles.packageTitle}>{pack.product.title || pack.identifier}</Text>
                    {isAnnual ? (
                      <View style={styles.bestValueBadge}>
                        <Text style={styles.bestValueBadgeText}>Best value</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.packagePrice}>{pack.product.priceString}</Text>
                </View>
              </AnimatedCard>
            );
          })}
        </View>
      )}

      {purchaseError ? <Text style={styles.error}>{purchaseError}</Text> : null}

      <TouchableOpacity
        style={[styles.primaryButton, (!selected || purchasing) && styles.primaryButtonDisabled]}
        onPress={() => selected && onPurchase(selected)}
        disabled={!selected || purchasing}
      >
        {purchasing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryButtonText}>Continue</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity onPress={onRestore} disabled={restoring} style={styles.restoreButton}>
        <Text style={styles.restoreButtonText}>
          {restoring ? 'Restoring…' : 'Restore purchases'}
        </Text>
      </TouchableOpacity>

      <Text style={styles.disclosure}>
        Payment is charged to your account at confirmation of purchase. Your subscription
        automatically renews unless auto-renew is turned off at least 24 hours before the end of
        the current period. Manage or cancel anytime in your device's account settings. By
        continuing, you agree to our{' '}
        <Text style={styles.disclosureLink} onPress={() => navigation.navigate('LegalPage', { pageKey: 'terms' })}>
          Terms of Use
        </Text>{' '}
        and{' '}
        <Text
          style={styles.disclosureLink}
          onPress={() => navigation.navigate('LegalPage', { pageKey: 'subscription_terms' })}
        >
          Subscription Terms
        </Text>
        .
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
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

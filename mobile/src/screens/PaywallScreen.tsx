import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import SectionHeading from '../components/SectionHeading';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { PACKAGE_TYPE, type PurchasesOffering, type PurchasesPackage } from 'react-native-purchases';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import {
  getCurrentOffering,
  purchasePackage,
  restorePurchases,
} from '../lib/revenuecat';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Paywall'>;

// Canonical source is modules/premium_page.py (PREMIUM_INCLUDED_NOW /
// MOBILE_PREMIUM_BENEFIT_LINES) — the same benefit list web's Premium page
// renders — fetched from GET /v1/me at render time. This copy is only the
// fallback for when that request fails, so it stays a plain string list that
// exactly matches the server's current canonical copy. Every line here
// corresponds to a real, server-enforced gate — see the paywall audit
// (2026-09-18). Don't add a benefit unless something in
// services/mobile_api_service.py actually withholds it from a Free account.
const FALLBACK_FEATURES = [
  'Your full Next Move briefing, not just the top 4',
  'Full League Pulse — see the whole league’s contenders and rebuilders',
  'The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist',
  'Every Trade Hub idea, not just the first 2 (skip the ads)',
  'GM Targets watchlist up to 50 players (Free is capped at 3)',
  'Portfolio — your record, rank, and top need across every saved league, not just one',
];

// Apple App Store Review Guideline 3.1.2 requires a subscription's length to
// be clearly displayed. `pack.product.title` is whatever display name is
// configured in App Store Connect/Play Console — it is not guaranteed to
// spell out the billing period, so the period shown on this screen is
// derived deterministically from RevenueCat's own `packageType` instead of
// trusting store-side copy to mention it. Keeps LIFETIME/CUSTOM/UNKNOWN safe
// (no current FantasyGM Lab offering uses them, but this must never render
// blank or throw if one is ever added).
function packagePeriodLabel(type: PurchasesPackage['packageType']): string {
  switch (type) {
    case PACKAGE_TYPE.ANNUAL:
      return 'Annual';
    case PACKAGE_TYPE.SIX_MONTH:
      return '6 Months';
    case PACKAGE_TYPE.THREE_MONTH:
      return '3 Months';
    case PACKAGE_TYPE.TWO_MONTH:
      return '2 Months';
    case PACKAGE_TYPE.MONTHLY:
      return 'Monthly';
    case PACKAGE_TYPE.WEEKLY:
      return 'Weekly';
    case PACKAGE_TYPE.LIFETIME:
      return 'Lifetime';
    default:
      return '';
  }
}

// Matches the billing cadence a periodLabel implies, for an explicit
// "$X.XX / year" (etc.) price line rather than a bare currency amount with
// no stated interval.
function packagePriceSuffix(type: PurchasesPackage['packageType']): string {
  switch (type) {
    case PACKAGE_TYPE.ANNUAL:
      return '/yr';
    case PACKAGE_TYPE.SIX_MONTH:
      return '/6mo';
    case PACKAGE_TYPE.THREE_MONTH:
      return '/3mo';
    case PACKAGE_TYPE.TWO_MONTH:
      return '/2mo';
    case PACKAGE_TYPE.MONTHLY:
      return '/mo';
    case PACKAGE_TYPE.WEEKLY:
      return '/wk';
    default:
      return '';
  }
}

export default function PaywallScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [offering, setOffering] = useState<PurchasesOffering | null>(null);
  const [features, setFeatures] = useState<string[]>(FALLBACK_FEATURES);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [purchasing, setPurchasing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [purchased, setPurchased] = useState(false);
  const mountedRef = useRef(true);

  // Shared by the initial load and pull-to-refresh so "Pull down to retry"
  // (below) is an accurate instruction rather than dead copy — previously
  // this only ever ran once on mount, with no way to recover from a failed
  // fetch short of leaving and re-entering the screen.
  const loadOffering = useCallback(async () => {
    try {
      const current = await getCurrentOffering();
      if (!mountedRef.current) return;
      setOffering(current);
      // Keyed off packageType (RevenueCat's own predefined-package enum), not
      // the offering's custom `identifier` string — the identifier is just
      // whatever this one offering happens to be named in the RevenueCat
      // dashboard, while packageType is the stable signal for "this is the
      // annual plan" regardless of naming.
      const preferred =
        current?.availablePackages.find((p) => p.packageType === PACKAGE_TYPE.ANNUAL) ??
        current?.availablePackages.find((p) => p.identifier === 'annual') ??
        current?.availablePackages[0] ??
        null;
      setSelectedId(preferred?.identifier ?? null);
      setLoadError(null);
    } catch {
      if (mountedRef.current) {
        setLoadError('Could not load subscription options. Pull down to retry.');
      }
    }
  }, []);

  // Independent of loadOffering: the benefit copy comes from the FantasyGM
  // Lab API (shared with web's Premium page), not the store, so one failing
  // shouldn't block the other. Any failure — network, auth, empty list —
  // silently keeps FALLBACK_FEATURES so the paywall never renders empty.
  const loadFeatures = useCallback(async () => {
    try {
      const me = await api.getMe();
      if (!mountedRef.current) return;
      if (Array.isArray(me.premium_benefits) && me.premium_benefits.length > 0) {
        setFeatures(me.premium_benefits);
      }
    } catch {
      // Keep FALLBACK_FEATURES.
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    (async () => {
      await Promise.allSettled([loadOffering(), loadFeatures()]);
      if (mountedRef.current) setLoading(false);
    })();
    return () => {
      mountedRef.current = false;
    };
  }, [loadOffering, loadFeatures]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.allSettled([loadOffering(), loadFeatures()]);
    if (mountedRef.current) setRefreshing(false);
  }, [loadOffering, loadFeatures]);

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
      <View style={styles.root}>
        <GridBackground />
        <View style={[styles.center, { paddingTop: headerHeight }]}>
          <Ionicons name="checkmark-circle" size={56} color={colors.success} style={styles.successIcon} />
          <AppText style={styles.successTitle}>You're on Premium</AppText>
          <AppText style={styles.successSubtitle}>
            It may take a moment to reflect everywhere in the app.
          </AppText>
          <TouchableOpacity style={styles.primaryButton} onPress={() => navigation.goBack()}>
            <AppText style={styles.primaryButtonText}>Done</AppText>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.root}>
    <GridBackground />
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
          colors={[colors.accent]}
        />
      }
    >
      <TouchableOpacity style={styles.closeButton} onPress={() => navigation.goBack()} hitSlop={8}>
        <AppText style={styles.closeButtonText}>Close</AppText>
      </TouchableOpacity>

      <AppText style={styles.title}>FantasyGM Lab Premium</AppText>
      <AppText style={styles.subtitle}>Founder Beta pricing — locked in for as long as you stay subscribed.</AppText>

      <SectionHeading title="What's Included" icon="checkmark-done" />
      <View style={styles.featuresCard}>
        {features.map((feature, index) => (
          <View key={feature} style={[styles.featureRow, index > 0 && styles.featureRowDivider]}>
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
        <>
          <SectionHeading title="Choose Your Plan" icon="card-outline" />
          <View style={styles.packages}>
            {packages.map((pack) => {
              const isSelected = pack.identifier === selectedId;
              // packageType (RevenueCat's predefined-package enum), not the
              // offering's custom `identifier` string — see loadOffering's
              // own note above.
              const isAnnual = pack.packageType === PACKAGE_TYPE.ANNUAL || pack.identifier === 'annual';
              const periodLabel = packagePeriodLabel(pack.packageType);
              const priceSuffix = packagePriceSuffix(pack.packageType);
              return (
                <AnimatedCard
                  key={pack.identifier}
                  glow={isAnnual}
                  onPress={() => setSelectedId(pack.identifier)}
                >
                  <View style={styles.packageRow}>
                    <Ionicons
                      name={isSelected ? 'radio-button-on' : 'radio-button-off'}
                      size={20}
                      color={isSelected ? colors.accent : colors.textTertiary}
                      style={styles.packageRadio}
                    />
                    <View style={styles.packageLabelGroup}>
                      <View style={styles.packageTitleRow}>
                        {/* Apple App Store Review Guideline 3.1.2: subscription
                            length must be clearly displayed — this is the bold,
                            primary label on every plan row, derived from
                            RevenueCat's own packageType rather than trusting
                            store-configured copy to mention it (see
                            packagePeriodLabel above). */}
                        <AppText style={styles.packageTitle}>
                          {periodLabel || pack.product.title || pack.identifier}
                        </AppText>
                        {isAnnual ? (
                          <View style={styles.bestValueBadge}>
                            <AppText style={styles.bestValueBadgeText}>Best value</AppText>
                          </View>
                        ) : null}
                      </View>
                      {/* Store-configured subscription title (3.1.2's other
                          requirement, distinct from the length above) — shown
                          only when it adds information beyond the period
                          label already shown. */}
                      {pack.product.title && pack.product.title !== periodLabel ? (
                        <AppText style={styles.packageSubtitle} numberOfLines={1}>
                          {pack.product.title}
                        </AppText>
                      ) : null}
                    </View>
                    <View style={styles.packagePriceGroup}>
                      <AppText style={styles.packagePrice}>
                        {pack.product.priceString}
                        {priceSuffix ? (
                          <AppText style={styles.packagePriceSuffix}>{priceSuffix}</AppText>
                        ) : null}
                      </AppText>
                      {/* Real SDK-provided equivalent monthly price (never a
                          client-computed approximation) — helps the annual
                          plan's value read clearly at a glance without
                          inventing a number RevenueCat didn't give us. */}
                      {isAnnual && pack.product.pricePerMonthString ? (
                        <AppText style={styles.packagePriceSub}>
                          {pack.product.pricePerMonthString}/mo
                        </AppText>
                      ) : null}
                    </View>
                  </View>
                </AnimatedCard>
              );
            })}
          </View>
        </>
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

      {/* Upgraded from a bare text link to a real bordered secondary button
          (same recipe LoginScreen's socialButton already uses: 1px border +
          surfaceSolid fill) — an earlier audit confirmed Restore Purchases
          existed, but "exists" and "genuinely easy to find" aren't the same
          thing on a screen this conversion-critical. Still visually
          subordinate to the cyan primary Continue button above it (Magna
          Carta button hierarchy), just no longer easy to miss entirely. */}
      <TouchableOpacity
        onPress={onRestore}
        disabled={restoring}
        style={[styles.restoreButton, restoring && styles.primaryButtonDisabled]}
      >
        {restoring ? (
          <ActivityIndicator color={colors.textPrimary} />
        ) : (
          <AppText style={styles.restoreButtonText}>Restore purchases</AppText>
        )}
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
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  closeButton: { alignSelf: 'flex-end', marginBottom: spacing.md },
  closeButtonText: { color: colors.textSecondary, fontSize: 15, fontWeight: '500' },
  title: { fontSize: 26, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.xs },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginBottom: spacing.xl, lineHeight: 20 },
  featuresCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.hairline,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.xl,
  },
  featureRow: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: spacing.sm + 2 },
  featureRowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.hairline },
  featureIcon: { marginRight: spacing.sm, marginTop: 1 },
  featureText: { flex: 1, color: colors.textPrimary, fontSize: 15, lineHeight: 21 },
  loadingIndicator: { marginVertical: spacing.xl },
  packages: { gap: spacing.sm, marginBottom: spacing.lg },
  packageRow: { flexDirection: 'row', alignItems: 'center' },
  packageRadio: { marginRight: spacing.sm },
  packageLabelGroup: { flex: 1, marginRight: spacing.sm },
  packageTitleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  packageTitle: { fontSize: 16, fontWeight: '600', color: colors.textPrimary },
  // Store-configured product title, shown under the period label — only
  // rendered when it says something the period label doesn't already.
  packageSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  packagePriceGroup: { alignItems: 'flex-end' },
  packagePrice: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  packagePriceSuffix: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  // Real RevenueCat-provided per-month equivalent for the annual plan — never
  // a client-side computed approximation.
  packagePriceSub: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
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
  primaryButtonDisabled: { opacity: disabledOpacity },
  primaryButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  restoreButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 48,
    marginTop: spacing.md,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSolid,
  },
  restoreButtonText: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  disclosure: {
    fontSize: 11,
    color: colors.textTertiary,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: spacing.xl,
  },
  disclosureLink: { color: colors.accent, fontWeight: '600' },
  error: { color: colors.danger, marginBottom: spacing.md },
  successIcon: { marginBottom: spacing.md },
  successTitle: { fontSize: 24, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
  successSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  });
}

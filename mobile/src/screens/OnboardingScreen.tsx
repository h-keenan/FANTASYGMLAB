import React, { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AppText from '../components/AppText';
import BrandMark from '../components/BrandMark';
import GlassPanel from '../components/GlassPanel';
import GridBackground from '../components/GridBackground';
import type { ExperienceLevelValue } from '../lib/api';
import { useExperienceLevel } from '../context/ExperienceLevelContext';
import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, typography, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Onboarding'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];
type ColorKey = 'accent' | 'premium' | 'success';

// One swipeable slide per feature, led by a real screenshot of that page in
// a phone frame with a one-line benefit below (owner, 2026-10-22: the old
// sample-card slide was "too basic"). Screenshots are captured from the real
// web UI against a generic sample league (no real users' data) and shared
// with web-next (public/onboarding/*.webp mirrors assets/onboarding/).
// Keep this list, its order and its copy in lockstep with web-next's
// OnboardingCarousel.tsx ONBOARDING_FEATURES. Flow: features -> connect ->
// experience level. (The mobile-only GM orb intro slide was dropped to match
// that flow.)
const FEATURES = [
  { key: 'gameplan', title: 'Game Plan', benefit: 'One clear top priority every time you open the app.', image: require('../../assets/onboarding/onboarding-gameplan.webp') },
  { key: 'tradehub', title: 'Trade Hub', benefit: 'Trade ideas your league partners would actually accept.', image: require('../../assets/onboarding/onboarding-tradehub.webp') },
  { key: 'matchup', title: 'Matchup', benefit: 'Win odds for your week, before kickoff.', image: require('../../assets/onboarding/onboarding-matchup.webp') },
  { key: 'planner', title: 'Lineup Planner', benefit: 'See what a swap does to your win odds.', image: require('../../assets/onboarding/onboarding-planner.webp') },
  { key: 'pqv', title: 'Player Quick View', benefit: 'Value, usage, and fit for any player in one tap.', image: require('../../assets/onboarding/onboarding-pqv.webp') },
  { key: 'playoff', title: 'Playoff Odds', benefit: 'Simulated playoff odds for every team in your league.', image: require('../../assets/onboarding/onboarding-playoff.webp') },
  { key: 'tendencies', title: 'Manager Tendencies', benefit: 'Know how each manager trades before you pitch.', image: require('../../assets/onboarding/onboarding-tendencies.webp') },
  { key: 'waivers', title: 'Waivers', benefit: 'Priority Adds ranked for your roster, with FAAB ranges.', image: require('../../assets/onboarding/onboarding-waivers.webp') },
] as const;

const STEP_KEYS = [...FEATURES.map((f) => f.key), 'connect', 'level'] as const;
type StepKey = (typeof STEP_KEYS)[number];
const PHONE_ASPECT = 600 / 1298;

const LEVEL_OPTIONS: { value: ExperienceLevelValue; icon: IconName; color: ColorKey; title: string; body: string }[] = [
  {
    value: 'beginner',
    icon: 'leaf-outline',
    color: 'success',
    title: 'New to dynasty',
    body: 'Explain the why behind every recommendation — trade logic, value, roster strategy.',
  },
  {
    value: 'advanced',
    icon: 'trophy-outline',
    color: 'premium',
    title: 'I know my stuff',
    body: 'Skip the explanations — just the call, the value, and the confidence.',
  },
];

/**
 * First-run intro carousel, shown once after sign-in (gated by
 * OnboardingContext) and replayable from More > "Replay intro tutorial".
 *
 * On a genuine first run it hands off to the Paywall as a skippable trial
 * offer (web-next's OnboardingCarousel -> OnboardingPaywall sequence), and
 * the Paywall finishes onboarding when it is dismissed. A replay just
 * returns to wherever it was opened from.
 */
export default function OnboardingScreen({ navigation }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  // Phone frame fills most of the slide but leaves room for the header,
  // eyebrow, one-line benefit and footer buttons.
  const phoneHeight = Math.max(240, Math.min(height * 0.56, 460));
  const { onboardingComplete, completeOnboarding, completeOnboardingViaGetStarted } = useOnboarding();
  const { setLevel: saveExperienceLevel } = useExperienceLevel();
  const scrollRef = useRef<ScrollView>(null);
  const [index, setIndex] = useState(0);
  const [level, setLevel] = useState<ExperienceLevelValue | null>(null);
  const [saving, setSaving] = useState(false);
  const isLast = index === STEP_KEYS.length - 1;
  // A replay from More starts with the flag already true; only a real
  // first run gets the trial-offer step.
  const isFirstRun = onboardingComplete === false;

  const goTo = (next: number) => {
    const clamped = Math.max(0, Math.min(STEP_KEYS.length - 1, next));
    setIndex(clamped);
    scrollRef.current?.scrollTo({ x: clamped * width, animated: true });
  };

  const onSkip = () => {
    if (isFirstRun) {
      navigation.navigate('Paywall', { fromOnboarding: 'skip' });
      return;
    }
    completeOnboarding();
    if (navigation.canGoBack()) navigation.goBack();
  };

  const onFinish = async () => {
    if (!level) return;
    setSaving(true);
    // Applies the beginner/advanced copy immediately and saves it to
    // /v1/preferences in the background. Best-effort, same as web: a failed
    // preference write never blocks onboarding.
    saveExperienceLevel(level);
    setSaving(false);
    if (isFirstRun) {
      navigation.navigate('Paywall', { fromOnboarding: 'getStarted' });
      return;
    }
    completeOnboardingViaGetStarted();
    if (navigation.canGoBack()) navigation.goBack();
  };

  const onMomentumScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = width > 0 ? Math.round(e.nativeEvent.contentOffset.x / width) : 0;
    setIndex(Math.max(0, Math.min(STEP_KEYS.length - 1, next)));
  };

  const renderStep = (key: StepKey) => {
    const feature = FEATURES.find((f) => f.key === key);
    if (feature) {
      return (
        <>
          <AppText style={styles.eyebrow}>{feature.title}</AppText>
          <View style={[styles.phoneFrame, { height: phoneHeight, width: phoneHeight * PHONE_ASPECT }]}>
            <Image
              source={feature.image}
              style={styles.phoneImage}
              resizeMode="cover"
              accessibilityLabel={`${feature.title} screen, shown with sample league data`}
            />
          </View>
          <AppText style={styles.benefit}>{feature.benefit}</AppText>
        </>
      );
    }
    switch (key) {
      case 'connect':
        return (
          <>
            <BrandMark width={112} style={styles.mark} />
            <AppText style={styles.eyebrow}>One setup step</AppText>
            <AppText style={styles.headlineSm}>Connect Sleeper or ESPN</AppText>
            <AppText style={styles.body}>Every recommendation is built around your league.</AppText>
          </>
        );
      case 'level':
        return (
          <>
            <AppText style={styles.eyebrow}>Last thing</AppText>
            <AppText style={styles.headlineSm}>How much dynasty experience do you have?</AppText>
            <AppText style={styles.body}>
              Tunes how much explanation shows up alongside recommendations. Change it anytime in Settings.
            </AppText>
            <View style={styles.cards}>
              {LEVEL_OPTIONS.map((option) => {
                const selected = level === option.value;
                return (
                  <TouchableOpacity
                    key={option.value}
                    onPress={() => setLevel(option.value)}
                    accessibilityRole="radio"
                    accessibilityState={{ selected }}
                    activeOpacity={0.85}
                  >
                    <GlassPanel style={selected ? [styles.pickCard, styles.pickCardSelected] : styles.pickCard}>
                      <View style={styles.pickHeader}>
                        <Ionicons name={option.icon} size={22} color={colors[option.color]} />
                        <AppText style={styles.rowTitle}>{option.title}</AppText>
                      </View>
                      <AppText style={styles.rowBody}>{option.body}</AppText>
                    </GlassPanel>
                  </TouchableOpacity>
                );
              })}
            </View>
          </>
        );
    }
  };

  const primaryLabel = !isLast ? 'Next' : isFirstRun ? 'Continue' : 'Done';
  const primaryDisabled = isLast && (!level || saving);

  return (
    <View style={styles.root}>
      <GridBackground />

      <View style={[styles.topRow, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.dotsRow}>
          {STEP_KEYS.map((key, i) => (
            <View key={key} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>
        <TouchableOpacity onPress={onSkip} hitSlop={12} accessibilityRole="button" accessibilityLabel="Skip tutorial">
          <AppText style={styles.skipText}>Skip</AppText>
        </TouchableOpacity>
      </View>

      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={onMomentumScrollEnd}
        style={styles.scroll}
      >
        {STEP_KEYS.map((key) => (
          <ScrollView
            key={key}
            style={{ width }}
            contentContainerStyle={styles.slide}
            showsVerticalScrollIndicator={false}
          >
            {renderStep(key)}
          </ScrollView>
        ))}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.lg }]}>
        <View style={styles.controlsRow}>
          {index > 0 ? (
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => goTo(index - 1)}
              accessibilityRole="button"
              accessibilityLabel="Previous slide"
            >
              <AppText style={styles.backText}>Back</AppText>
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity
            style={[styles.primaryButton, primaryDisabled && styles.primaryButtonDisabled]}
            onPress={() => (isLast ? void onFinish() : goTo(index + 1))}
            disabled={primaryDisabled}
            accessibilityRole="button"
            accessibilityLabel={isLast ? primaryLabel : 'Next slide'}
          >
            {saving ? (
              <ActivityIndicator color={colors.onAccent} />
            ) : (
              <AppText style={styles.primaryText}>{primaryLabel}</AppText>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    topRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacing.lg,
      paddingBottom: spacing.xs,
      zIndex: 1,
    },
    skipText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    scroll: { flex: 1 },
    slide: {
      flexGrow: 1,
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: spacing.xl,
      paddingVertical: spacing.lg,
    },
    mark: { marginBottom: spacing.xl },
    eyebrow: {
      fontSize: 13,
      fontWeight: '700',
      letterSpacing: 1,
      textTransform: 'uppercase',
      color: colors.accent,
      marginBottom: spacing.sm,
      textAlign: 'center',
    },
    headline: {
      ...typography.title,
      color: colors.textPrimary,
      textAlign: 'center',
      marginBottom: spacing.md,
    },
    headlineSm: {
      ...typography.title,
      fontSize: 22,
      lineHeight: 28,
      color: colors.textPrimary,
      textAlign: 'center',
      marginBottom: spacing.md,
    },
    body: {
      ...typography.body,
      color: colors.textSecondary,
      textAlign: 'center',
      lineHeight: 22,
      maxWidth: 340,
    },
    cards: { alignSelf: 'stretch', gap: spacing.sm, marginTop: spacing.md },
    phoneFrame: {
      marginTop: spacing.sm,
      borderWidth: 5,
      borderColor: colors.borderStrong,
      borderRadius: radii.lg,
      backgroundColor: colors.background,
      overflow: 'hidden',
    },
    phoneImage: { width: '100%', height: '100%' },
    benefit: {
      ...typography.body,
      fontSize: 17,
      fontWeight: '600',
      color: colors.textPrimary,
      textAlign: 'center',
      lineHeight: 24,
      maxWidth: 320,
      marginTop: spacing.md,
    },
    rowTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    rowBody: { fontSize: 13, lineHeight: 19, color: colors.textSecondary, marginTop: 2 },
    pickCard: { padding: spacing.md, borderWidth: 1.5, borderColor: 'transparent' },
    pickCardSelected: { borderColor: colors.accent },
    pickHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs },
    footer: { paddingHorizontal: spacing.xl, paddingTop: spacing.sm },
    dotsRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    dot: { width: 7, height: 7, borderRadius: radii.pill, backgroundColor: colors.border },
    dotActive: { width: 20, backgroundColor: colors.accent },
    controlsRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    backButton: {
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.border,
    },
    backText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    primaryButton: {
      flex: 1,
      backgroundColor: colors.accent,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      alignItems: 'center',
    },
    primaryButtonDisabled: { opacity: disabledOpacity },
    primaryText: { fontSize: 16, fontWeight: '600', color: colors.onAccent },
  });
}

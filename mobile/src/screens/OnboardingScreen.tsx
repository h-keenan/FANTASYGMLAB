import React, { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
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
import { disabledOpacity, radii, shadows, spacing, typography, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Onboarding'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];
type ColorKey = 'accent' | 'premium' | 'success';

const STEP_KEYS = ['who', 'solve', 'how', 'orb', 'level'] as const;
type StepKey = (typeof STEP_KEYS)[number];

// Steps 'who' / 'solve' / 'how' / 'level' are a port of web-next's
// OnboardingCarousel.tsx (Zach, 2026-10-18: "at least 3 pgs on sign up abt
// who we are and what we solve and how it works and ask if the user is a
// beginner or advanced"), copy verbatim from that component. Its step-1
// copy is itself the coridian_-approved (2026-09-26) mobile copy, so do not
// rephrase without re-checking with product. 'orb' is the one mobile-only
// step: web's carousel omits it only because the GM orb doesn't exist on web.

const SOLVE_ROWS: { icon: IconName; color: ColorKey; title: string; body: string }[] = [
  {
    icon: 'swap-horizontal-outline',
    color: 'premium',
    title: 'Trade Hub',
    body: 'Real, believable trade ideas — ones your league partners would actually say yes to.',
  },
  {
    icon: 'add-circle-outline',
    color: 'success',
    title: 'Waivers',
    body: 'Priority Adds ranked for your roster, not a generic most-added list.',
  },
  {
    icon: 'flash-outline',
    color: 'accent',
    title: 'Next Move',
    body: 'One clear top priority every time you open the app.',
  },
];

const HOW_STEPS: { color: ColorKey; title: string; body: string }[] = [
  {
    color: 'accent',
    title: 'Connect your Sleeper league',
    body: 'The one setup step. Every recommendation depends on it.',
  },
  {
    color: 'premium',
    title: 'Get your Game Plan',
    body: 'The Dashboard leads with your top priority action first.',
  },
  {
    color: 'success',
    title: 'Make your move',
    body: 'Act straight from Trade Hub or Waivers — recommendation and action, same place.',
  },
];

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
  const { width } = useWindowDimensions();
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
    switch (key) {
      case 'who':
        return (
          <>
            <BrandMark width={112} style={styles.mark} />
            <AppText style={styles.eyebrow}>Who we are</AppText>
            <AppText style={styles.headline}>Your fantasy front office, not just a stats app.</AppText>
            <AppText style={styles.body}>
              Real recommendations across your Trade Hub, Waivers, and Next Move — not raw data you have to
              interpret yourself.
            </AppText>
          </>
        );
      case 'solve':
        return (
          <>
            <AppText style={styles.eyebrow}>What we solve</AppText>
            <AppText style={styles.headlineSm}>{'Dynasty data is everywhere.\nDecisions are hard.'}</AppText>
            <View style={styles.cards}>
              {SOLVE_ROWS.map((row) => (
                <GlassPanel key={row.title} style={styles.rowCard}>
                  <Ionicons name={row.icon} size={20} color={colors[row.color]} style={styles.rowIcon} />
                  <View style={styles.rowText}>
                    <AppText style={styles.rowTitle}>{row.title}</AppText>
                    <AppText style={styles.rowBody}>{row.body}</AppText>
                  </View>
                </GlassPanel>
              ))}
            </View>
          </>
        );
      case 'how':
        return (
          <>
            <AppText style={styles.eyebrow}>How it works</AppText>
            <AppText style={styles.headlineSm}>Three steps. That's it.</AppText>
            <View style={styles.cards}>
              {HOW_STEPS.map((step, i) => (
                <View key={step.title} style={styles.howRow}>
                  <View style={[styles.stepNumber, { backgroundColor: colors[step.color] }]}>
                    <AppText style={styles.stepNumberText}>{i + 1}</AppText>
                  </View>
                  <GlassPanel style={styles.howCard}>
                    <AppText style={styles.rowTitle}>{step.title}</AppText>
                    <AppText style={styles.rowBody}>{step.body}</AppText>
                  </GlassPanel>
                </View>
              ))}
            </View>
          </>
        );
      case 'orb':
        return (
          <>
            <View style={styles.orbHalo}>
              <View style={styles.orbCore}>
                <BrandMark width={40} />
              </View>
            </View>
            <AppText style={styles.eyebrow}>Getting around</AppText>
            <AppText style={styles.headline}>Meet the GM orb</AppText>
            <AppText style={styles.body}>
              This single floating control gets you anywhere — your leagues, GM Tools, everything else. There is
              no bottom nav. This is it.
            </AppText>
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
    rowCard: { flexDirection: 'row', alignItems: 'flex-start', padding: spacing.md },
    rowIcon: { marginRight: spacing.md, marginTop: 2 },
    rowText: { flex: 1 },
    rowTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    rowBody: { fontSize: 13, lineHeight: 19, color: colors.textSecondary, marginTop: 2 },
    howRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    stepNumber: {
      width: 28,
      height: 28,
      borderRadius: radii.pill,
      alignItems: 'center',
      justifyContent: 'center',
    },
    stepNumberText: { fontSize: 14, fontWeight: '800', color: colors.onAccent },
    howCard: { flex: 1, padding: spacing.md },
    pickCard: { padding: spacing.md, borderWidth: 1.5, borderColor: 'transparent' },
    pickCardSelected: { borderColor: colors.accent },
    pickHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs },
    // Stylized stand-in for the GM orb (not the real animated component):
    // an accent-tinted halo around a small core carrying the FD mark.
    orbHalo: {
      width: 132,
      height: 132,
      borderRadius: 66,
      backgroundColor: colors.accentMuted,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: spacing.xl,
    },
    orbCore: {
      width: 68,
      height: 68,
      borderRadius: 34,
      backgroundColor: colors.background,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.accent,
      alignItems: 'center',
      justifyContent: 'center',
      ...shadows.orbGlow,
    },
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

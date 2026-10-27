import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
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
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withTiming,
} from 'react-native-reanimated';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AppText from '../components/AppText';
import Button from '../components/Button';
import BrandMark from '../components/BrandMark';
import GlassPanel from '../components/GlassPanel';
import OnboardingAurora from '../components/OnboardingAurora';
import type { ExperienceGoalValue, ExperienceLevelValue } from '../lib/api';
import { EXPERIENCE_GOAL_OPTIONS, EXPERIENCE_LEVEL_OPTIONS, PLAIN_COPY } from '../lib/experienceCopy';
import { useExperienceLevel } from '../context/ExperienceLevelContext';
import { experienceBucket, trackOnboarding, trackOnboardingStepViewed } from '../lib/onboardingAnalytics';
import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors } from '../theme';
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
// onboardingFeatures.ts ONBOARDING_FEATURES. Signup flow is 3 steps
// (coridian_, 2026-10-23: "10 is insane"): value -> connect -> level. The
// value step auto-advances through VALUE_SLIDE_KEYS inside one step; the full
// 8-screen list is only used by the replay tour (More > Replay the tour).
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

const STEP_KEYS = ['value', 'connect', 'level'] as const;
type StepKey = (typeof STEP_KEYS)[number] | (typeof FEATURES)[number]['key'];
const VALUE_SLIDE_KEYS = ['gameplan', 'tradehub', 'matchup', 'waivers'] as const;
const VALUE_HEADLINE = 'Know your best move every week.';
const VALUE_SLIDE_MS = 3600;
const VALUE_SLIDES = VALUE_SLIDE_KEYS.map((k) => FEATURES.find((f) => f.key === k)!);
const PHONE_ASPECT = 600 / 1298;

// Web parity (globals.css onboarding-slide-next/back): 0.28s ease-out,
// opacity 0 -> 1 and a 24px horizontal nudge toward the final position.
// Opacity/transform only, on the UI thread; skipped under reduced motion.
const SLIDE_NUDGE_PX = 24;
const SLIDE_MS = 280;

function SlideIn({ active, direction, children }: { active: boolean; direction: 'next' | 'back'; children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();
  const progress = useSharedValue(1);
  const sign = direction === 'next' ? 1 : -1;
  useLayoutEffect(() => {
    // Inactive slides stay fully visible so a swipe in progress never shows
    // a blank incoming page; only the slide that becomes active nudges in.
    if (reduceMotion || !active) {
      progress.value = 1;
      return;
    }
    progress.value = 0;
    progress.value = withTiming(1, { duration: SLIDE_MS, easing: Easing.out(Easing.ease) });
  }, [active, reduceMotion, progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateX: (1 - progress.value) * SLIDE_NUDGE_PX * sign }],
  }));
  return <Animated.View style={[styles_slideFill, style]}>{children}</Animated.View>;
}
const styles_slideFill = { alignItems: 'center' as const, alignSelf: 'stretch' as const };

// "Signal" stagger (web parity: .onboarding-slide > * rise, 70ms apart):
// each child of the active step fades up 14px, one after another. Opacity and
// transform only; skipped under reduced motion.
const RISE_PX = 14;
const RISE_MS = 480;
const RISE_STAGGER_MS = 70;

function Rise({ active, index, children }: { active: boolean; index: number; children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();
  const progress = useSharedValue(1);
  useLayoutEffect(() => {
    if (reduceMotion || !active) {
      progress.value = 1;
      return;
    }
    progress.value = 0;
    progress.value = withDelay(
      Math.min(index, 4) * RISE_STAGGER_MS,
      withTiming(1, { duration: RISE_MS, easing: Easing.out(Easing.cubic) }),
    );
  }, [active, index, reduceMotion, progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: (1 - progress.value) * RISE_PX }],
  }));
  return <Animated.View style={[styles_slideFill, style]}>{children}</Animated.View>;
}

/** Wraps each top-level child of a step (unwrapping one fragment) in <Rise>. */
function staggered(node: React.ReactNode, active: boolean): React.ReactNode {
  const parts =
    React.isValidElement<{ children?: React.ReactNode }>(node) && node.type === React.Fragment
      ? React.Children.toArray(node.props.children)
      : React.Children.toArray(node);
  return parts.map((part, i) => (
    <Rise key={i} active={active} index={i}>
      {part}
    </Rise>
  ));
}

// web: .onboarding-dot transition width/background 0.2s; active = 20px accent.
function ProgressDot({ active, color, activeColor }: { active: boolean; color: string; activeColor: string }) {
  const reduceMotion = useReducedMotion();
  const w = useSharedValue(active ? 20 : 7);
  useEffect(() => {
    w.value = reduceMotion ? (active ? 20 : 7) : withTiming(active ? 20 : 7, { duration: 200 });
  }, [active, reduceMotion, w]);
  const style = useAnimatedStyle(() => ({ width: w.value }));
  return (
    <Animated.View
      style={[
        { height: 7, borderRadius: 999, backgroundColor: active ? activeColor : color },
        active ? { shadowColor: activeColor, shadowOpacity: 0.9, shadowRadius: 6, shadowOffset: { width: 0, height: 0 } } : null,
        style,
      ]}
    />
  );
}

// Titles/bodies come from the shared EXPERIENCE_LEVEL_OPTIONS (lib/
// experienceCopy.ts) so this never drifts from web's onboarding picker or
// either platform's Settings mirror — only icon/color stay mobile-only.
const LEVEL_OPTIONS: { value: ExperienceLevelValue; icon: IconName; color: ColorKey; title: string; body: string }[] = [
  {
    value: 'new_to_fantasy',
    icon: 'sparkles-outline',
    color: 'accent',
    ...EXPERIENCE_LEVEL_OPTIONS.new_to_fantasy,
  },
  {
    value: 'beginner',
    icon: 'leaf-outline',
    color: 'success',
    ...EXPERIENCE_LEVEL_OPTIONS.beginner,
  },
  {
    value: 'advanced',
    icon: 'trophy-outline',
    color: 'premium',
    ...EXPERIENCE_LEVEL_OPTIONS.advanced,
  },
];

const GOAL_OPTIONS: { value: ExperienceGoalValue; label: string }[] = (
  Object.keys(EXPERIENCE_GOAL_OPTIONS) as ExperienceGoalValue[]
).map((value) => ({ value, label: EXPERIENCE_GOAL_OPTIONS[value].label }));

/**
 * First-run intro carousel, shown once after sign-in (gated by
 * OnboardingContext) and replayable from More > "Replay intro tutorial".
 *
 * On a genuine first run it hands off to the Paywall as a skippable trial
 * offer (web-next's OnboardingCarousel -> OnboardingPaywall sequence), and
 * the Paywall finishes onboarding when it is dismissed. A replay just
 * returns to wherever it was opened from.
 */
function isReplayRoute(route: Props['route'] | undefined): boolean {
  return route?.params?.replay === true;
}

export default function OnboardingScreen({ navigation, route }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  // Phone frame fills most of the slide but leaves room for the header,
  // eyebrow, one-line benefit and footer buttons.
  const phoneHeight = Math.max(240, Math.min(height * 0.56, 460));
  // The value step adds a headline and preview controls above/below.
  const valuePhoneHeight = Math.max(200, Math.min(height * 0.44, 380));
  const { onboardingComplete, completeOnboarding, completeOnboardingViaGetStarted } = useOnboarding();
  const { setLevel: saveExperienceLevel, setGoal: saveExperienceGoal } = useExperienceLevel();
  const scrollRef = useRef<ScrollView>(null);
  const [index, setIndex] = useState(0);
  const prevIndex = useRef(0);
  const direction: 'next' | 'back' = index >= prevIndex.current ? 'next' : 'back';
  useEffect(() => {
    prevIndex.current = index;
  }, [index]);
  const [level, setLevel] = useState<ExperienceLevelValue | null>(null);
  // Optional, skippable — never gates the primary button, unlike level.
  const [goal, setGoal] = useState<ExperienceGoalValue | null>(null);
  const [valueSlide, setValueSlide] = useState(0);
  const [valuePaused, setValuePaused] = useState(false);
  const reduceMotion = useReducedMotion();
  const valueAuto = !isReplayRoute(route) && index === 0 && !valuePaused && !reduceMotion;
  useEffect(() => {
    if (!valueAuto) return;
    const id = setInterval(() => setValueSlide((s) => (s + 1) % VALUE_SLIDES.length), VALUE_SLIDE_MS);
    return () => clearInterval(id);
  }, [valueAuto]);
  const [saving, setSaving] = useState(false);
  // Replay (More > "Replay the tour"): feature slides only. No connect or
  // experience step, so no preference is written, no funnel events fire and
  // the onboarding-completed flag is never touched.
  const isReplay = isReplayRoute(route);
  const stepKeys: readonly StepKey[] = isReplay ? FEATURES.map((f) => f.key) : STEP_KEYS;
  const isLast = index === stepKeys.length - 1;
  // A replay from More starts with the flag already true; only a real
  // first run gets the trial-offer step.
  const isFirstRun = onboardingComplete === false;

  // One step_viewed per step per session (deduped in the helper).
  useEffect(() => {
    if (isReplay) return;
    trackOnboardingStepViewed(STEP_KEYS[index], index);
  }, [index, isReplay]);

  const goTo = (next: number) => {
    const clamped = Math.max(0, Math.min(stepKeys.length - 1, next));
    if (clamped < index && !isReplay) trackOnboarding('back', { step: STEP_KEYS[index], step_index: index });
    setIndex(clamped);
    scrollRef.current?.scrollTo({ x: clamped * width, animated: true });
  };

  const onSkip = () => {
    if (isReplay) {
      if (navigation.canGoBack()) navigation.goBack();
      return;
    }
    trackOnboarding('skipped', { step: STEP_KEYS[index], step_index: index });
    if (isFirstRun) {
      navigation.navigate('Paywall', { fromOnboarding: 'skip' });
      return;
    }
    completeOnboarding();
    if (navigation.canGoBack()) navigation.goBack();
  };

  const onFinish = async () => {
    if (isReplay) {
      if (navigation.canGoBack()) navigation.goBack();
      return;
    }
    if (!level) return;
    trackOnboarding('completed', { step: 'level', step_index: index, experience: experienceBucket(level) });
    setSaving(true);
    // Applies the beginner/advanced copy immediately and saves it to
    // /v1/preferences in the background. Best-effort, same as web: a failed
    // preference write never blocks onboarding.
    saveExperienceLevel(level);
    // Optional, so only saved when the user actually picked one. Also
    // best-effort, same as the level write above.
    if (goal) saveExperienceGoal(goal);
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
    setIndex(Math.max(0, Math.min(stepKeys.length - 1, next)));
  };

  const renderStep = (key: StepKey) => {
    if (key === 'value') {
      const current = VALUE_SLIDES[valueSlide];
      return (
        <>
          <AppText style={styles.eyebrow}>{current.title}</AppText>
          <AppText style={styles.headlineSm} accessibilityRole="header">
            {VALUE_HEADLINE.slice(0, VALUE_HEADLINE.lastIndexOf(' ') + 1)}
            <AppText style={styles.headlineAccent}>{VALUE_HEADLINE.slice(VALUE_HEADLINE.lastIndexOf(' ') + 1)}</AppText>
          </AppText>
          <View style={[styles.phoneFrame, { height: valuePhoneHeight, width: valuePhoneHeight * PHONE_ASPECT }]}>
            <Image
              source={current.image}
              style={styles.phoneImage}
              resizeMode="cover"
              accessibilityLabel={`${current.title} screen, shown with sample league data`}
            />
          </View>
          <AppText style={styles.benefit}>{current.benefit}</AppText>
          <View style={styles.valueControls}>
            <View style={styles.dotsRow} accessibilityLabel="Preview screens">
              {VALUE_SLIDES.map((s, i) => (
                <TouchableOpacity
                  key={s.key}
                  onPress={() => {
                    setValueSlide(i);
                    setValuePaused(true);
                  }}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel={`Show ${s.title}`}
                  accessibilityState={{ selected: i === valueSlide }}
                  style={styles.valueDotHit}
                >
                  <View style={[styles.dot, i === valueSlide && styles.dotActive]} />
                </TouchableOpacity>
              ))}
            </View>
            {!reduceMotion ? (
              <TouchableOpacity
                onPress={() => setValuePaused((p) => !p)}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={valuePaused ? 'Play previews' : 'Pause previews'}
              >
                <AppText style={styles.backText}>{valuePaused ? 'Play previews' : 'Pause previews'}</AppText>
              </TouchableOpacity>
            ) : null}
          </View>
        </>
      );
    }
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
            <AppText style={styles.headlineSm}>
              Connect <AppText style={styles.headlineAccent}>Sleeper or ESPN</AppText>
            </AppText>
            <AppText style={styles.body}>Every recommendation is built around your league.</AppText>
          </>
        );
      case 'level':
        return (
          <>
            <AppText style={styles.eyebrow}>Last thing</AppText>
            <AppText style={styles.headlineSm}>
              How much dynasty <AppText style={styles.headlineAccent}>experience</AppText> do you have?
            </AppText>
            <AppText style={styles.body}>
              Tunes how much explanation shows up alongside recommendations. Change it anytime in Settings.
            </AppText>
            <AppText style={styles.body}>{PLAIN_COPY.onboardingDynastyNote}</AppText>
            <View style={styles.cards}>
              {LEVEL_OPTIONS.map((option) => {
                const selected = level === option.value;
                return (
                  <TouchableOpacity
                    key={option.value}
                    onPress={() => {
                      setLevel(option.value);
                      trackOnboarding('experience_selected', { experience: experienceBucket(option.value) });
                    }}
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
            <AppText style={[styles.body, styles.goalPrompt]}>{PLAIN_COPY.experienceGoalPrompt}</AppText>
            <View style={styles.goalChipRow}>
              {GOAL_OPTIONS.map((option) => {
                const selected = goal === option.value;
                return (
                  <TouchableOpacity
                    key={option.value}
                    onPress={() => setGoal((current) => (current === option.value ? null : option.value))}
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    activeOpacity={0.85}
                    style={[styles.goalChip, selected && styles.goalChipSelected]}
                  >
                    <AppText style={[styles.goalChipLabel, selected && styles.goalChipLabelSelected]}>{option.label}</AppText>
                  </TouchableOpacity>
                );
              })}
            </View>
            <AppText style={styles.goalOptionalNote}>{PLAIN_COPY.experienceGoalOptionalNote}</AppText>
          </>
        );
    }
  };

  const primaryLabel = !isLast ? 'Next' : isFirstRun ? 'Continue' : 'Done';
  const primaryDisabled = isLast && !isReplay && (!level || saving);

  return (
    <View style={styles.root}>
      <OnboardingAurora cyan={colors.accent} violet={colors.violet} />
      <View style={[styles.topRow, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.dotsRow}>
          {stepKeys.map((key, i) => (
            <ProgressDot key={key} active={i === index} color={colors.border} activeColor={colors.accent} />
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
        {stepKeys.map((key) => (
          <ScrollView
            key={key}
            style={{ width }}
            contentContainerStyle={styles.slide}
            showsVerticalScrollIndicator={false}
          >
            <SlideIn active={stepKeys[index] === key} direction={direction}>
              {staggered(renderStep(key), stepKeys[index] === key)}
            </SlideIn>
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
          <Button
            label={primaryLabel}
            onPress={() => (isLast ? void onFinish() : goTo(index + 1))}
            disabled={primaryDisabled}
            loading={saving}
            style={styles.primaryButton}
          />
        </View>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
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
    headlineAccent: { color: colors.accent, fontWeight: '800' },
    headlineSm: {
      ...typography.title,
      fontWeight: '800',
      letterSpacing: -0.3,
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
    goalPrompt: { marginTop: spacing.lg, maxWidth: undefined },
    goalChipRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: spacing.sm, marginTop: spacing.sm },
    goalChip: {
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: radii.pill,
      borderWidth: 1.5,
      borderColor: colors.border,
    },
    goalChipSelected: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    goalChipLabel: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
    goalChipLabelSelected: { color: colors.textPrimary },
    goalOptionalNote: { fontSize: 12, color: colors.textTertiary, textAlign: 'center', marginTop: spacing.xs },
    valueControls: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg, marginTop: spacing.sm },
    valueDotHit: { paddingVertical: 8, paddingHorizontal: 3 },
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
      shadowColor: colors.accent,
      shadowOpacity: 0.45,
      shadowRadius: 14,
      shadowOffset: { width: 0, height: 0 },
    },
  });
}

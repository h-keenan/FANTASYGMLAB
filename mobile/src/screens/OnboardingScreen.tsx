import React, { useMemo, useRef, useState } from 'react';
import {
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
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, shadows, spacing, typography, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Onboarding'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];

interface Slide {
  key: string;
  icon: IconName;
  headline: string;
  body: string;
  /** Slide 3 gets a stylized "orb" visual instead of a plain IconCircle. */
  isOrbSlide?: boolean;
}

// Copy approved by coridian_ via Discord brainstorm (2026-09-26) — do not
// rephrase without re-checking with product.
const SLIDES: Slide[] = [
  {
    key: 'welcome',
    icon: 'briefcase-outline',
    headline: 'Your fantasy front office, not just a stats app.',
    body: 'Real recommendations across your Trade Hub, Waivers, and Next Move — not raw data you have to interpret yourself.',
  },
  {
    key: 'connect-league',
    icon: 'checkmark-done-circle-outline',
    headline: 'Connect your Sleeper league',
    body: "Importing your league from Sleeper is the one setup step. Every recommendation depends on it, so it's the first thing to do.",
  },
  {
    key: 'gm-orb',
    icon: 'ellipse',
    isOrbSlide: true,
    headline: 'Meet the GM orb',
    body: 'This single floating control gets you anywhere — your leagues, GM Tools, everything else. There is no bottom nav. This is it.',
  },
  {
    key: 'next-move',
    icon: 'flag-outline',
    headline: 'Your Next Move is home base',
    body: 'The Dashboard leads with your top priority action first. Everything else on the page supports that one call.',
  },
  {
    key: 'team-stance',
    icon: 'compass-outline',
    headline: "Tell us your team's situation",
    body: 'Rebuilding, Competing, or Balanced — so trade and waiver advice actually matches your GM philosophy instead of generic advice.',
  },
];

/**
 * First-launch value-first tutorial — a 5-slide carousel shown once after
 * sign-in (gated by OnboardingContext) and re-playable from More > About >
 * "Replay intro tutorial". Content is intentionally static/local: no
 * network calls, no business logic, nothing that could drift from the
 * live app and go stale — it only orients a new user toward screens/
 * concepts that already exist.
 *
 * Reuses GridBackground/IconCircle/theme tokens rather than inventing new
 * illustration assets (per the task brief) — the GM-orb slide is the one
 * exception, given a stylized stand-in built from existing shadow/color
 * tokens rather than importing the real (animated, stateful) GmOrb
 * component into a screen that shouldn't depend on its navigation sheet.
 */
export default function OnboardingScreen({ navigation }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { completeOnboarding } = useOnboarding();
  const scrollRef = useRef<ScrollView>(null);
  const [index, setIndex] = useState(0);
  const isLast = index === SLIDES.length - 1;

  const goTo = (next: number) => {
    const clamped = Math.max(0, Math.min(SLIDES.length - 1, next));
    setIndex(clamped);
    scrollRef.current?.scrollTo({ x: clamped * width, animated: true });
  };

  // Shared by Skip and the final "Get Started": marks the flag complete
  // (a no-op write if it's already true, e.g. a replay from More) and, when
  // this screen was pushed on top of something (replay case), pops back to
  // it. When this is the first-run gating screen there's nothing to pop —
  // RootNavigator's onboardingComplete flip remounts the stack onto Home.
  const finish = () => {
    completeOnboarding();
    if (navigation.canGoBack()) navigation.goBack();
  };

  const onMomentumScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = width > 0 ? Math.round(e.nativeEvent.contentOffset.x / width) : 0;
    setIndex(Math.max(0, Math.min(SLIDES.length - 1, next)));
  };

  return (
    <View style={styles.root}>
      <GridBackground />

      <View style={[styles.skipRow, { paddingTop: insets.top + spacing.sm }]}>
        <TouchableOpacity
          onPress={finish}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Skip tutorial"
        >
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
        {SLIDES.map((slide) => (
          <View key={slide.key} style={[styles.slide, { width }]}>
            {slide.isOrbSlide ? (
              <View style={styles.orbHalo}>
                <View style={styles.orbCore}>
                  <Ionicons name={slide.icon} size={30} color={colors.accent} />
                </View>
              </View>
            ) : (
              <IconCircle
                name={slide.icon}
                color={colors.accent}
                size={96}
                iconSize={44}
                style={styles.iconCircle}
              />
            )}
            <AppText style={styles.headline}>{slide.headline}</AppText>
            <AppText style={styles.body}>{slide.body}</AppText>
          </View>
        ))}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.lg }]}>
        <View style={styles.dotsRow}>
          {SLIDES.map((slide, i) => (
            <View key={slide.key} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>
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
            style={styles.primaryButton}
            onPress={() => (isLast ? finish() : goTo(index + 1))}
            accessibilityRole="button"
            accessibilityLabel={isLast ? 'Get Started' : 'Next slide'}
          >
            <AppText style={styles.primaryText}>{isLast ? 'Get Started' : 'Next'}</AppText>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    skipRow: {
      alignItems: 'flex-end',
      paddingHorizontal: spacing.lg,
      paddingBottom: spacing.xs,
      zIndex: 1,
    },
    skipText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    scroll: { flex: 1 },
    slide: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingHorizontal: spacing.xl,
    },
    iconCircle: { marginBottom: spacing.xl },
    // Stylized stand-in for the GM orb: a soft accent-tinted halo (echoing
    // the real orb's shadows.orbGlow treatment) around a small solid core —
    // reads as "a glowing floating control" without importing or
    // reimplementing the actual animated component.
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
    headline: {
      ...typography.title,
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
    footer: { paddingHorizontal: spacing.xl, paddingTop: spacing.sm },
    dotsRow: {
      flexDirection: 'row',
      justifyContent: 'center',
      alignItems: 'center',
      gap: spacing.xs,
      marginBottom: spacing.lg,
    },
    dot: {
      width: 7,
      height: 7,
      borderRadius: radii.pill,
      backgroundColor: colors.border,
    },
    dotActive: {
      width: 20,
      backgroundColor: colors.accent,
    },
    controlsRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
    },
    backButton: {
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      borderRadius: radii.sm,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.border,
    },
    backText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    primaryButton: {
      flex: 1,
      backgroundColor: colors.accent,
      borderRadius: radii.sm,
      paddingVertical: spacing.md,
      alignItems: 'center',
    },
    primaryText: { fontSize: 16, fontWeight: '600', color: '#fff' },
  });
}

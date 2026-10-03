import React, { useMemo } from 'react';
import { Pressable, StyleSheet, ViewStyle, type PressableProps } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

import { useThemeMode } from '../context/ThemeModeContext';
import { glowShadow, gradients, lightGradients, motion, radii, shadows, spacing, type ThemeColors } from '../theme';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

interface AnimatedCardProps extends PressableProps {
  style?: ViewStyle;
  children: React.ReactNode;
  /** A thin accent-gradient rim + colored glow instead of the plain hairline
   * border — reserved for the one or two most important cards on a screen
   * (e.g. Dashboard's Top Priority card). Not meant for every card: per
   * coridian_'s "distinct accents, but don't overdo it," this stays rare on
   * purpose so it still reads as "this one matters" when it shows up. */
  glow?: boolean;
  /** Overrides the glow rim gradient and drop shadow with a single solid
   * color instead of the universal brand cyan. For a card whose own content
   * already carries a semantic/category color (icon, ring, headline number),
   * passing that same color here keeps the rim+shadow and the content
   * reading as one accent instead of two unrelated ones clashing (e.g.
   * RecapScreen's hero card, matched to its featured story's category).
   * Ignored unless `glow` is also set. */
  glowColor?: string;
}

/**
 * The app's single card primitive: solid #151B22 fill, 16pt radius, an
 * Apple-style dark-mode shadow (a plain black shadow reads as a smudge on
 * near-black, so a subtle top-edge highlight is layered in to make the card
 * read as physically raised), and a quick spring press animation matching
 * iOS's native list-row/button feel. `style` can override padding/layout
 * exactly as before — the highlight overlay shares the card's own top
 * corner radius rather than needing a separate clipped wrapper, so it never
 * fights a caller's padding.
 */
export default function AnimatedCard({ style, children, glow, glowColor, onPressIn, onPressOut, ...rest }: AnimatedCardProps) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const scale = useSharedValue(1);
  const shadowT = useSharedValue(0); // 0 = resting, 1 = pressed

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));
  const highlightStyle = useAnimatedStyle(() => ({
    opacity: 0.05 - shadowT.value * 0.03,
  }));

  const pressable = (
    <AnimatedPressable
      style={[styles.card, glow && styles.cardGlowInner, style, animatedStyle]}
      onPressIn={(e) => {
        scale.value = withSpring(0.97, motion.pressSpring);
        shadowT.value = withSpring(1, motion.pressSpring);
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        scale.value = withSpring(1, motion.pressSpring);
        shadowT.value = withSpring(0, motion.pressSpring);
        onPressOut?.(e);
      }}
      {...rest}
    >
      <Animated.View pointerEvents="none" style={[styles.highlight, highlightStyle]} />
      {children}
    </AnimatedPressable>
  );

  if (!glow) return pressable;

  const rimColors = glowColor ? ([glowColor, glowColor] as const) : isDark ? gradients.accent : lightGradients.accent;
  const rimShadow = glowColor ? glowShadow(glowColor) : shadows.orbGlow;

  return (
    <LinearGradient colors={rimColors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.glowRim, rimShadow]}>
      {pressable}
    </LinearGradient>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    ...shadows.resting,
  },
  highlight: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '35%',
    borderTopLeftRadius: radii.md,
    borderTopRightRadius: radii.md,
    backgroundColor: '#FFFFFF',
  },
  // Shadow is applied at render time (default `shadows.orbGlow`, or
  // `glowShadow(glowColor)` when a caller overrides the rim color) rather
  // than baked in here, so a single `glow` card can tint its own drop
  // shadow instead of always inheriting brand cyan.
  glowRim: {
    borderRadius: radii.md,
    padding: 1.5,
  },
  cardGlowInner: { borderWidth: 0 },
  });
}

import React from 'react';
import { Pressable, StyleSheet, ViewStyle, type PressableProps } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';

import { colors, motion, radii, shadows, spacing } from '../theme';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

interface AnimatedCardProps extends PressableProps {
  style?: ViewStyle;
  children: React.ReactNode;
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
export default function AnimatedCard({ style, children, onPressIn, onPressOut, ...rest }: AnimatedCardProps) {
  const scale = useSharedValue(1);
  const shadowT = useSharedValue(0); // 0 = resting, 1 = pressed

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));
  const highlightStyle = useAnimatedStyle(() => ({
    opacity: 0.05 - shadowT.value * 0.03,
  }));

  return (
    <AnimatedPressable
      style={[styles.card, style, animatedStyle]}
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
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
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
});

import React from 'react';
import { Pressable, StyleSheet, ViewStyle, type PressableProps } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';

import { cardShadow, colors, radii, spacing } from '../theme';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

interface AnimatedCardProps extends PressableProps {
  style?: ViewStyle;
  children: React.ReactNode;
}

/**
 * A card surface that scales down slightly on press, matching the native
 * "tap feedback" feel (iOS/Android system list rows both do a subtle
 * press-in). Used anywhere a whole row/card is tappable.
 */
export default function AnimatedCard({ style, children, onPressIn, onPressOut, ...rest }: AnimatedCardProps) {
  const scale = useSharedValue(1);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <AnimatedPressable
      style={[styles.card, style, animatedStyle]}
      onPressIn={(e) => {
        scale.value = withSpring(0.97, { damping: 18, stiffness: 300 });
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        scale.value = withSpring(1, { damping: 18, stiffness: 300 });
        onPressOut?.(e);
      }}
      {...rest}
    >
      {children}
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: spacing.lg,
    ...cardShadow,
  },
});

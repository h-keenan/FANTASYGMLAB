import React, { useEffect } from 'react';
import { Platform, type StyleProp, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { useThemeMode } from '../context/ThemeModeContext';

/**
 * The gold glow every premium control and surface wears (owner, 2026-10-23),
 * the prestige-ring recipe (PlayerAvatar's PrestigeGlow: a slow ease-in-out
 * pulse) applied as a soft gold shadow halo. Static when `pulse` is off, when
 * `active` is false (disabled / loading) or when the OS asks for reduced
 * motion. Shadow only, so it never shifts layout. iOS draws the shadowRadius
 * halo; Android falls back to a gold-tinted elevation. Mirrors web's
 * `.premium-glow` / `.premium-glow-card`.
 */
export default function PremiumGlow({
  children,
  style,
  radius = 12,
  pulse = true,
  active = true,
  strength = 1,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  /** Corner radius of the glowing shape (the shadow follows it). */
  radius?: number;
  pulse?: boolean;
  active?: boolean;
  /** 1 for a button, ~0.6 for a large card. */
  strength?: number;
}) {
  const { colors } = useThemeMode();
  const reduceMotion = useReducedMotion();
  const progress = useSharedValue(0);
  const animate = active && pulse && !reduceMotion;

  useEffect(() => {
    if (animate) {
      progress.value = withRepeat(withTiming(1, { duration: 2500, easing: Easing.inOut(Easing.ease) }), -1, true);
    } else {
      progress.value = 0.5;
    }
  }, [animate, progress]);

  const animatedStyle = useAnimatedStyle(() => ({
    shadowOpacity: (0.35 + progress.value * 0.3) * strength,
    shadowRadius: 8 + progress.value * 6,
  }));

  if (!active) return <Animated.View style={style}>{children}</Animated.View>;
  return (
    <Animated.View
      style={[
        {
          borderRadius: radius,
          shadowColor: colors.premiumGlow,
          shadowOffset: { width: 0, height: 0 },
          ...(Platform.OS === 'android' ? { elevation: 6 * strength } : {}),
        },
        style,
        animatedStyle,
      ]}
    >
      {children}
    </Animated.View>
  );
}

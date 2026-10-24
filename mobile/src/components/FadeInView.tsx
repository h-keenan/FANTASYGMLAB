import React, { useEffect, useRef } from 'react';
import { AccessibilityInfo, Animated, type StyleProp, type ViewStyle } from 'react-native';

/**
 * Fades (opacity) and nudges (translateY) its children in over ~150ms when
 * mounted. Opacity/transform only, so layout never moves; skipped entirely
 * when the OS asks for reduced motion.
 */
export default function FadeInView({
  children,
  style,
  durationMs = 150,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  durationMs?: number;
}) {
  const progress = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled()
      .catch(() => false)
      .then((reduce) => {
        if (cancelled) return;
        if (reduce) {
          progress.setValue(1);
          return;
        }
        Animated.timing(progress, { toValue: 1, duration: durationMs, useNativeDriver: true }).start();
      });
    return () => {
      cancelled = true;
    };
  }, [progress, durationMs]);
  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [4, 0] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

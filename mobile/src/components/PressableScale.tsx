import React, { forwardRef } from 'react';
import { AccessibilityInfo, Pressable, type PressableProps, type StyleProp, type View, type ViewStyle } from 'react-native';

import { pressFeedback } from '../lib/motion';

/**
 * THE tappable (twin of web-next's global press rule, lib/motion.ts PRESS): a drop-in for TouchableOpacity that shows the one
 * press feedback, a 3% shrink and a slight fade while held, released on lift. Under OS Reduce Motion it keeps the fade and drops
 * the shrink. Every Button, row, pill, tab and chip in the app presses through this, so they all feel the same.
 * `pressFeedback={false}` opts out only for a control that already animates itself (GM orb, AnimatedCard).
 */
let reducedNow = false;
let subscribed = false;
function ensureReducedMotionWatch() {
  if (subscribed) return;
  subscribed = true;
  AccessibilityInfo.isReduceMotionEnabled?.()
    .then((v) => {
      reducedNow = Boolean(v);
    })
    .catch(() => {});
  AccessibilityInfo.addEventListener?.('reduceMotionChanged', (v) => {
    reducedNow = Boolean(v);
  });
}

export interface PressableScaleProps extends Omit<PressableProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  /** false: no press feedback (the control animates itself). */
  pressFeedback?: boolean;
}

const PressableScale = forwardRef<View, PressableScaleProps>(function PressableScale({ style, pressFeedback: feedback = true, disabled, ...rest }, ref) {
  ensureReducedMotionWatch();
  return (
    <Pressable
      ref={ref}
      disabled={disabled}
      style={({ pressed }) => {
        if (!feedback) return style;
        const f = pressFeedback(pressed, reducedNow, Boolean(disabled));
        return pressed && !disabled ? [style, { opacity: f.opacity, transform: [{ scale: f.scale }] }] : style;
      }}
      {...rest}
    />
  );
});

export default PressableScale;

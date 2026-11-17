import * as Haptics from 'expo-haptics';

import { effectsPrefs } from './effectsPrefs';
import { createHaptics, type HapticIntent, type HapticStep } from './hapticCore';

export type { HapticIntent } from './hapticCore';

const IMPACT = {
  light: Haptics.ImpactFeedbackStyle.Light,
  medium: Haptics.ImpactFeedbackStyle.Medium,
  rigid: Haptics.ImpactFeedbackStyle.Rigid,
  heavy: Haptics.ImpactFeedbackStyle.Heavy,
} as const;
const NOTIFY = {
  success: Haptics.NotificationFeedbackType.Success,
  warning: Haptics.NotificationFeedbackType.Warning,
  error: Haptics.NotificationFeedbackType.Error,
} as const;

function drive(step: HapticStep) {
  if (step.kind === 'impact') return Haptics.impactAsync(IMPACT[step.style]);
  if (step.kind === 'selection') return Haptics.selectionAsync();
  return Haptics.notificationAsync(NOTIFY[step.type]);
}

/**
 * THE haptic entry point (the only file allowed to import expo-haptics; check_motion_usage enforces it).
 * `haptic('commit')`. Named intents only, never throws, throttled, off when the Settings "Haptics" toggle is off.
 * Never call it from a passive live update (a pushed score): only from something the user just did.
 * Safe from a worklet via `runOnJS(haptic)('lift')`.
 */
export const haptic: (intent: HapticIntent) => void = createHaptics({
  driver: drive,
  isEnabled: () => effectsPrefs.get().haptics,
});

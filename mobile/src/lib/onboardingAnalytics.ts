import { trackUse } from './analytics';

/**
 * Privacy-safe onboarding funnel events (feature_use / onboarding), same
 * shape as web-next/src/lib/onboardingAnalytics.ts. Fixed snake_case ids
 * only; `step_viewed` once per step per app session. No-ops while
 * EXPO_PUBLIC_ANALYTICS_ENABLED is off (the analytics core drops events).
 */
const viewedSteps = new Set<string>();

export function resetOnboardingAnalytics(): void {
  viewedSteps.clear();
}

export function trackOnboarding(
  action: string,
  props?: { step?: string; step_index?: number; experience?: 'new' | 'expert' },
): void {
  trackUse('onboarding', action, { props: { ...(props ?? {}) } });
}

export function trackOnboardingStepViewed(step: string, stepIndex: number): void {
  if (viewedSteps.has(step)) return;
  viewedSteps.add(step);
  trackOnboarding('step_viewed', { step, step_index: stepIndex });
}

/** Both beginner-ish levels ("new_to_fantasy" and "beginner") bucket as
 * "new" — the funnel keeps its original two buckets even though the picker
 * itself grew a third, more granular level. */
export function experienceBucket(level: string): 'new' | 'expert' {
  return level === 'beginner' || level === 'new_to_fantasy' ? 'new' : 'expert';
}

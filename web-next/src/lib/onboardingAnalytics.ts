import { trackUse } from "./analytics";

/**
 * Privacy-safe onboarding funnel events: `feature_use` feature=onboarding.
 * Props are fixed snake_case ids / indices only (step, step_index,
 * experience) -- never names, emails or free text. `step_viewed` is sent once
 * per step per page session so a re-render or Back/Next revisit never double
 * counts. Mirrored by mobile/src/lib/onboardingAnalytics.ts.
 */
const viewedSteps = new Set<string>();

export function resetOnboardingAnalytics(): void {
  viewedSteps.clear();
}

export function trackOnboarding(
  action: string,
  props?: { step?: string; step_index?: number; experience?: "new" | "expert" },
): void {
  trackUse("onboarding", action, { props: { ...(props || {}) } });
}

export function trackOnboardingStepViewed(step: string, stepIndex: number): void {
  if (viewedSteps.has(step)) return;
  viewedSteps.add(step);
  trackOnboarding("step_viewed", { step, step_index: stepIndex });
}

/** Experience picker value -> the funnel's new|expert split. Both
 * beginner-ish levels ("new_to_fantasy" and "beginner") bucket as "new" —
 * the funnel keeps its original two buckets even though the picker itself
 * grew a third, more granular level. */
export function experienceBucket(level: string): "new" | "expert" {
  return level === "beginner" || level === "new_to_fantasy" ? "new" : "expert";
}

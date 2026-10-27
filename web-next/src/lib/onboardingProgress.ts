/**
 * Per-account, per-browser record of which pre-league onboarding steps were
 * already completed or skipped, so a signed-in user who still has no saved
 * league is not walked through the carousel and trial offer again on every
 * visit to "/". Booleans only; best effort (storage can be blocked).
 */
export type OnboardingStep = "carousel" | "paywall";

const key = (userId: string, step: OnboardingStep) => `fgl:onboarding:${step}:${userId}`;

export function hasCompletedOnboardingStep(userId: string | null | undefined, step: OnboardingStep): boolean {
  if (!userId) return false;
  try {
    return window.localStorage.getItem(key(userId, step)) === "1";
  } catch {
    return false;
  }
}

export function markOnboardingStepCompleted(userId: string | null | undefined, step: OnboardingStep): void {
  if (!userId) return;
  try {
    window.localStorage.setItem(key(userId, step), "1");
  } catch {
    // Best effort.
  }
}

/**
 * Per-account, per-browser record of which pre-league onboarding steps were
 * already completed or skipped, so a signed-in user who still has no saved
 * league is not walked through the carousel and trial offer again on every
 * visit to "/". Booleans only; best effort (storage can be blocked).
 */
export type OnboardingStep = "carousel" | "paywall" | "offer_armed";

/**
 * "paywall" now means the trial offer card was resolved (dismissed or
 * opened). "offer_armed" is set when the first league connects, so only
 * accounts that went through that first connect ever see the card.
 */

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

/** Where this account's trial offer stands, for lib/firstRunFlow.ts. */
export function trialOfferState(userId: string | null | undefined): "idle" | "armed" | "dismissed" {
  if (hasCompletedOnboardingStep(userId, "paywall")) return "dismissed";
  return hasCompletedOnboardingStep(userId, "offer_armed") ? "armed" : "idle";
}

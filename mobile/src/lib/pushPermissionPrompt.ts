/**
 * Pure gating for the in-app notification pre-prompt (coridian_, 2026-10-24:
 * ask AFTER the user's first league has loaded, never at sign-in). No RN
 * imports so it runs under node --test. The OS prompt only ever fires after
 * the user taps "Turn on" on our own pre-prompt.
 */

export type PushPermissionState = 'granted' | 'denied' | 'undetermined' | 'unsupported';

/** "Not now" suppresses the pre-prompt for this long. */
export const PUSH_PROMPT_COOLDOWN_MS = 14 * 24 * 60 * 60 * 1000;

/** Normalize a stored "Not now" timestamp; anything unusable means "never dismissed". */
export function parseDismissedAt(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function isPushPromptCoolingDown(dismissedAt: number | null, now: number): boolean {
  if (dismissedAt === null) return false;
  const elapsed = now - dismissedAt;
  // A timestamp in the future (clock change) only counts within one cooldown
  // window, so a bad clock can't suppress the prompt forever.
  if (elapsed < 0) return Math.abs(elapsed) < PUSH_PROMPT_COOLDOWN_MS;
  return elapsed < PUSH_PROMPT_COOLDOWN_MS;
}

export function shouldShowPushPrePrompt(input: {
  permission: PushPermissionState;
  /** A league's Dashboard has successfully loaded data for the signed-in user. */
  leagueLoaded: boolean;
  dismissedAt: number | null;
  now: number;
  /** Already shown/handled this app session. */
  askedThisSession?: boolean;
}): boolean {
  if (!input.leagueLoaded) return false;
  if (input.askedThisSession) return false;
  // Granted: nothing to ask. Denied: the OS won't show a prompt again, so the
  // only path is the Settings toggle. Unsupported (simulator): pointless.
  if (input.permission !== 'undetermined') return false;
  return !isPushPromptCoolingDown(input.dismissedAt, input.now);
}

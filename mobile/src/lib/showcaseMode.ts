/**
 * Showcase / privacy mode — a recording mode that swaps every real person's
 * identity out of the UI so App Store / marketing screenshots can be taken
 * from a live account without exposing league members' usernames, team
 * names, league names, avatars or the account email. Shown in the app as
 * "Privacy mode" (More > Developer, founder accounts only).
 *
 * Two halves:
 *   1. Availability — the legacy email allowlist (below) OR a Supabase Auth
 *      `app_metadata.founder_ops` claim (the same claim that gates web's
 *      Founder Analytics page). Nobody else ever sees the toggle.
 *   2. Masking — one central engine (lib/privacyMask.ts, a copy of
 *      web-next/src/lib/privacy.ts): generic labels ("Manager 1", "Team A",
 *      "Sample League"), avatars dropped (initials from the generic label),
 *      email hidden, known names scrubbed from free text.
 *      `authorizedRequest` in lib/api.ts masks every response and un-masks
 *      every outgoing body (masking is display-only), so one flag covers the
 *      whole app; screens that read `saved_leagues` straight from Supabase
 *      (Home, GM Orb / league switcher) call it directly.
 *
 * Deliberately NOT masked: player names, positions, NFL teams, scores,
 * values, headshots — all the football data is the point of the footage.
 */
import { createMasker, type MaskKind } from './privacyMask.ts';

/**
 * Dev account emails allowed to use showcase mode. Emails are compared
 * case-insensitively after trimming.
 */
export const SHOWCASE_MODE_EMAILS: string[] = ['keenanhf@outlook.com'];

/** True when the signed-in account may use privacy mode at all. */
export function isShowcaseModeAvailable(
  email: string | null | undefined,
  appMetadata?: Record<string, unknown> | null,
): boolean {
  if (appMetadata?.founder_ops === true) return true;
  if (!email) return false;
  const normalized = email.trim().toLowerCase();
  if (!normalized) return false;
  return SHOWCASE_MODE_EMAILS.some((allowed) => allowed.trim().toLowerCase() === normalized);
}

/**
 * Module-level because the masking runs inside `api.ts`, a plain module with
 * no access to React context. `ShowcaseModeProvider` pushes the current
 * value here in an effect (via `api.setShowcaseModeEnabled`).
 */
let showcaseModeEnabled = false;

const masker = createMasker();

export function setShowcaseModeEnabled(enabled: boolean): void {
  showcaseModeEnabled = enabled;
}

export function isShowcaseModeEnabled(): boolean {
  return showcaseModeEnabled;
}

/**
 * Deep-clones `value` with every identity field replaced. A no-op (same
 * reference back) whenever the mode is off, so the normal path pays nothing.
 */
export function maskShowcaseFields<T>(value: T): T {
  if (!showcaseModeEnabled) return value;
  return masker.mask(value);
}

/** Restores real values in an outgoing request body: a masked label is never
 * sent to the server. A no-op while the mode is off. */
export function unmaskShowcaseFields<T>(value: T): T {
  if (!showcaseModeEnabled) return value;
  return masker.unmask(value);
}

/** Masks a single display string that never came through a JSON payload
 * (the signed-in account's own email on Home, for instance). */
export function maskShowcaseText(pool: 'team' | 'league' | 'owner' | 'username' | 'email', value: string | null | undefined): string | null | undefined {
  if (!showcaseModeEnabled || !value) return value;
  if (pool === 'email') return 'hidden@example.com';
  const kind: MaskKind = pool === 'owner' ? 'person' : pool === 'username' ? 'handle' : pool;
  return masker.label(kind, value);
}

/** Fresh label state (tests). */
export function resetShowcaseMaskForTests(): void {
  showcaseModeEnabled = false;
}

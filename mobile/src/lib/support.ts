/**
 * Single source for the help / feedback entry. Mirrors web-next/src/lib/support.ts
 * (a test keeps the address and label byte-identical).
 *
 * NOTE: the support@fantasydesk.app mailbox MX may not be live yet
 * (docs/LOGIC-AND-BASES-AUDIT-2026-10-28.md O3). Until it is, mail to this
 * address can bounce; swap the constant here (one place) if a different
 * inbox or a form replaces it.
 */
export const SUPPORT_EMAIL = "support@fantasydesk.app";
export const HELP_LINK_LABEL = "Something wrong? Tell us";

export interface SupportContext {
  /** Short fixed id for where the user was, e.g. "connect_error". */
  topic?: string;
  /** League platform when known (sleeper, espn, ...). */
  platform?: string | null;
  leagueId?: string | null;
  /** Free-form line, e.g. the error message shown. */
  detail?: string | null;
}

export function supportMailto(ctx: SupportContext = {}, appVersion = "app"): string {
  const lines = [
    "",
    "",
    "---",
    "Please keep these details so we can find the problem:",
    `Where: ${ctx.topic ?? "general"}`,
    ctx.platform ? `Platform: ${ctx.platform}` : null,
    ctx.leagueId ? `League id: ${ctx.leagueId}` : null,
    ctx.detail ? `Message: ${ctx.detail}` : null,
    `App: ${appVersion}`,
  ].filter((line): line is string => line !== null);
  const subject = "FantasyDesk help";
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join("\n"))}`;
}

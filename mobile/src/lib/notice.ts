// The one in-app notice (toast) timing and wording rules for the app (UI pass 5 D7, coridian_ 2026-11-14). Pure (no React, no react-native) so
// the app's node tests can run it. Errors stay a little longer than confirmations; a newer notice replaces the one on screen.

export type NoticeTone = 'error' | 'success' | 'info';

export const NOTICE_MS: Record<NoticeTone, number> = { success: 3000, info: 3500, error: 5000 };

/** "Could not update Watchlist" + "Please try again in a moment." -> one sentence-cased line. */
export function noticeText(title: string, detail?: string): string {
  const head = title.trim().replace(/[.!]+$/, '');
  const tail = detail?.trim();
  return tail ? `${head}. ${tail}` : head;
}

/** The tone a legacy alert title implies: "Could not ..." / "failed" / "full" are errors, "... sent|saved|copied" confirmations. */
export function noticeToneFor(title: string): NoticeTone {
  if (/^could not|failed|unable|full\b|required|no device/i.test(title.trim())) return 'error';
  if (/\b(sent|saved|copied|done|updated)\b/i.test(title)) return 'success';
  return 'info';
}

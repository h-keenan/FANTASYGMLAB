/**
 * Pure logic for the shared compact module (`CompactModule`, docs/ui-patterns.md): a card that is genuinely
 * informative while collapsed (a dense one or two line summary with the key numbers and status) and expands on
 * tap. Import-free, byte-identical twin of mobile/src/lib/compactModule.ts. Also holds the auto-dismiss rule of the
 * shared notice toast, so web and app never disagree on how long a confirmation stays up.
 */

export type CompactTone = "success" | "danger" | "warning" | "muted" | "accent" | "action";

/** One piece of the collapsed summary line: "R1 P2", "You pick now", "need RB/WR". */
export interface CompactPart {
  key: string;
  text: string;
  tone?: CompactTone;
  /** Drawn bold (the one thing that matters: the status, the deadline). */
  strong?: boolean;
}

/** A summary reads in one or two lines on a phone; more parts than this stops being a summary. */
export const COMPACT_MAX_PARTS = 6;

/** Drop empty/falsy parts and cap the line, keeping order. */
export function compactParts(parts: ReadonlyArray<CompactPart | null | undefined | false | "">, max: number = COMPACT_MAX_PARTS): CompactPart[] {
  const out: CompactPart[] = [];
  for (const part of parts) {
    if (!part || !part.text || !part.text.trim()) continue;
    out.push(part);
    if (out.length >= max) break;
  }
  return out;
}

/** The plain-text form of a summary (screen readers, tests): "R1 P2 · You pick now · 0:42". */
export function compactSummaryText(parts: ReadonlyArray<CompactPart>): string {
  return parts.map((p) => p.text.trim()).join(" · ");
}

/** The accessible name of the header button: title, then the summary, then the state. */
export function compactAriaLabel(title: string, parts: ReadonlyArray<CompactPart>, open: boolean): string {
  const summary = compactSummaryText(parts);
  return `${title}${summary ? `: ${summary}` : ""}. ${open ? "Collapse" : "Expand"}`;
}

/** "R2 P5" style short counts: "3 offers", "1 offer", "No offers". */
export function compactCount(n: number, one: string, many?: string, none?: string): string {
  if (n <= 0) return none ?? `No ${many ?? `${one}s`}`;
  return `${n} ${n === 1 ? one : (many ?? `${one}s`)}`;
}

export type NoticeToastTone = "success" | "danger" | "warning" | "muted" | "accent";

/**
 * How long a confirmation stays on screen before it removes itself. A result the user caused ("Trade completed",
 * "Waiver claimed") is just feedback and goes after a few seconds; a warning lingers a little longer; an error never
 * auto-dismisses (it needs a decision) so null.
 */
export function noticeDismissMs(tone: NoticeToastTone): number | null {
  if (tone === "danger") return null;
  if (tone === "warning") return 7000;
  return 4000;
}

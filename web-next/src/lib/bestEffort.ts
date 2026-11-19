import { reportError } from "@/lib/errorReporter";

const reported = new Set<string>();

/**
 * Catch handler for an OPTIONAL enrichment read whose card is allowed to stay hidden when it fails (a secondary module on a
 * page that is otherwise fine). The failure is still reported once per label per session to the error reporter, so a card
 * that is quietly broken for everyone shows up instead of looking like "nothing to show". Never throws. User-visible loads
 * must use the shared ErrorState instead (docs/audits/2026-11-silent-failures.md).
 */
export function bestEffort(label: string): (error: unknown) => void {
  return (error) => {
    if (reported.has(label)) return;
    reported.add(label);
    reportError(error, { best_effort: label });
  };
}

import { reportError } from './errorReporter';

const reported = new Set<string>();

/**
 * Catch handler for an OPTIONAL enrichment read whose card may stay hidden when it fails. The failure is still reported
 * once per label per session, so a quietly broken card shows up. User-visible loads must use the shared ErrorState.
 * Twin of web's lib/bestEffort.ts.
 */
export function bestEffort(label: string): (error: unknown) => void {
  return (error) => {
    if (reported.has(label)) return;
    reported.add(label);
    reportError(error, { best_effort: label });
  };
}

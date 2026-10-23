/** Labels for the Trade Analyzer's branded share card (matches web-next's
 * /share-card/analyzer card: a "For <partner>" line and the ACCEPT/DECLINE/
 * COUNTER/FAIR grade as the big word). */

const GRADES = new Set(['ACCEPT', 'DECLINE', 'COUNTER', 'FAIR']);

/** "For Rival GM", or null when no trade partner was picked. */
export function partnerForLine(partnerTeamName: string | null | undefined): string | null {
  const name = (partnerTeamName ?? '').trim();
  return name ? `For ${name}` : null;
}

/** The analyzer's grade word, or null for anything else (e.g. Trade Hub's
 * 'IDEA'), so callers fall back to the value-edge band. */
export function analyzerHeadline(uiVerdict: string | null | undefined): string | null {
  const grade = (uiVerdict ?? '').trim().toUpperCase();
  return GRADES.has(grade) ? grade : null;
}

import { bandToken, percentBand, probabilityBand, toneToken, verdictBand, type VerdictBand } from "./verdictTone";

/** CSS colour for a band (web). The map itself lives in verdictTone.ts, shared with the app. */
export function bandColorVar(band: VerdictBand): string {
  return `var(--color-${bandToken(band)})`;
}

export const probabilityColorVar = (p: number | null | undefined): string => bandColorVar(probabilityBand(p));
export const percentColorVar = (pct: number | null | undefined): string => bandColorVar(percentBand(pct));
export const verdictColorVar = (v: string | null | undefined): string => bandColorVar(verdictBand(v));

/** CSS colour for a grade tone slug (web). The map itself is toneToken in verdictTone.ts, shared with the app. */
export function toneColorVar(tone: string | null | undefined): string {
  const token = toneToken(tone);
  return token === "muted" ? "var(--color-text-muted)" : `var(--color-${token})`;
}

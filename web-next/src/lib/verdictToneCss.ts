import { bandToken, percentBand, probabilityBand, verdictBand, type VerdictBand } from "./verdictTone";

/** CSS colour for a band (web). The map itself lives in verdictTone.ts, shared with the app. */
export function bandColorVar(band: VerdictBand): string {
  return `var(--color-${bandToken(band)})`;
}

export const probabilityColorVar = (p: number | null | undefined): string => bandColorVar(probabilityBand(p));
export const percentColorVar = (pct: number | null | undefined): string => bandColorVar(percentBand(pct));
export const verdictColorVar = (v: string | null | undefined): string => bandColorVar(verdictBand(v));

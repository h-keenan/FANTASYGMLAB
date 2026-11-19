import type { ThemeColors } from '../theme';
import { bandToken, percentBand, probabilityBand, toneToken, verdictBand, type VerdictBand } from './verdictTone';

/** Theme colour for a band (app). The map itself lives in verdictTone.ts, shared with web. */
export function bandColor(colors: ThemeColors, band: VerdictBand): string {
  const token = bandToken(band);
  if (token === 'success') return colors.successBright;
  if (token === 'warning') return colors.warning;
  if (token === 'danger') return colors.danger;
  return colors.textSecondary;
}

export const probabilityColor = (colors: ThemeColors, p: number | null | undefined): string => bandColor(colors, probabilityBand(p));
export const percentColor = (colors: ThemeColors, pct: number | null | undefined): string => bandColor(colors, percentBand(pct));
export const verdictColor = (colors: ThemeColors, v: string | null | undefined): string => bandColor(colors, verdictBand(v));

/** Theme colour for a grade tone slug (app). The map itself is toneToken in verdictTone.ts, shared with web. */
export function toneColor(colors: ThemeColors, tone: string | null | undefined): string {
  const token = toneToken(tone);
  if (token === 'success') return colors.success;
  if (token === 'accent') return colors.accent;
  if (token === 'warning') return colors.warning;
  return colors.textSecondary;
}

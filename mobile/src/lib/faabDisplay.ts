import type { WaiverFaabGuidance } from './api';

/**
 * Display text for a waiver recommendation's FAAB guidance. Mirrors
 * modules/faab.py's FaabGuidance.as_label(): dollars when the league's
 * remaining budget is known, a percent-of-pool range otherwise, and — in
 * leagues without FAAB (Sleeper rolling / reverse-standings waivers) or when
 * the bid is missing — a claim label with no dollar figure at all.
 */
export function faabDisplayText(faab: WaiverFaabGuidance | null | undefined): {
  isBid: boolean;
  primary: string;
  secondary: string;
} {
  if (faab == null || faab.applicable === false) {
    const secondary =
      faab?.waiver_mode === 'rolling'
        ? 'Rolling waivers · no FAAB'
        : faab?.waiver_mode === 'reverse_standings'
          ? 'Reverse-standings waivers · no FAAB'
          : 'No FAAB bid';
    return { isBid: false, primary: 'Waiver claim', secondary };
  }
  const hasDollars = faab.dollars_known && faab.remaining != null;
  return {
    isBid: true,
    primary: hasDollars ? `$${faab.low_bid}–$${faab.high_bid}` : `${faab.pct_low}–${faab.pct_high}%`,
    secondary: hasDollars ? `of $${faab.remaining} remaining` : 'of remaining FAAB',
  };
}

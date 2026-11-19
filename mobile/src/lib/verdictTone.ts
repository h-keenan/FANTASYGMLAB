/**
 * THE shared probability / verdict colour map (UI audit batch C, docs/ui-patterns.md "Verdict colours").
 * Import-free, byte-identical twin of mobile/src/lib/verdictTone.ts (scripts/check_lib_twins.mjs).
 *
 * Rules:
 *  - A verdict SENTENCE ("Your opponent is on track to win") is neutral text, never coloured, and its card has no
 *    semantic border. Semantic colour lives only on small chips / badges / pills / numbers beside it.
 *  - Every win %, playoff / title odds figure and verdict word picks its tone HERE, so the same number reads the same
 *    colour on Today, Matchup, Trades, Trade Analyzer, Waivers and the Sim pages.
 *  - Bands: good (green), neutral (secondary text), caution (amber), bad (red, chips only).
 *  - Negative deltas are not "bad": they use deltaBand (muted + a down arrow), green only for positive.
 */

export type VerdictBand = "good" | "neutral" | "caution" | "bad";

/** Probability cut points (0..1): >= good is good, >= neutral is neutral, >= caution is caution, otherwise bad. */
export const PROBABILITY_CUTS = { good: 0.6, neutral: 0.4, caution: 0.2 } as const;

/** A 0..1 probability (win chance, playoff odds, title odds) -> band. Missing or non-finite reads neutral. */
export function probabilityBand(probability: number | null | undefined): VerdictBand {
  if (typeof probability !== "number" || !Number.isFinite(probability)) return "neutral";
  if (probability >= PROBABILITY_CUTS.good) return "good";
  if (probability >= PROBABILITY_CUTS.neutral) return "neutral";
  if (probability >= PROBABILITY_CUTS.caution) return "caution";
  return "bad";
}

/** The same map for a 0..100 percentage. */
export function percentBand(percent: number | null | undefined): VerdictBand {
  return typeof percent === "number" && Number.isFinite(percent) ? probabilityBand(percent / 100) : "neutral";
}

/**
 * The one-word read of a win chance, from the SAME bands as the colour (>= 60% Favored, 40-60% Toss-up, 20-40% Underdog,
 * below that Long shot). Every "57% win" label and every "Even / Favored" word beside it comes from here, so a number and
 * its label can never disagree. Missing reads "".
 */
export function probabilityWord(probability: number | null | undefined): string {
  if (typeof probability !== "number" || !Number.isFinite(probability)) return "";
  const band = probabilityBand(probability);
  return band === "good" ? "Favored" : band === "neutral" ? "Toss-up" : band === "caution" ? "Underdog" : "Long shot";
}

/** The same word for a 0..100 percentage. */
export function percentWord(percent: number | null | undefined): string {
  return typeof percent === "number" && Number.isFinite(percent) ? probabilityWord(percent / 100) : "";
}

/** A verdict word from any surface (trade accept/decline/counter/fair, positive/risk, success/danger...) -> band. */
export function verdictBand(verdict: string | null | undefined): VerdictBand {
  switch (verdict) {
    case "accept":
    case "positive":
    case "success":
    case "good":
    case "worked_out":
      return "good";
    case "decline":
    case "risk":
    case "danger":
    case "bad":
    case "negative":
    case "didnt_pan_out":
      return "bad";
    case "counter":
    case "caution":
    case "warning":
    case "mixed":
      return "caution";
    default:
      return "neutral";
  }
}

/** A signed change (margin, edge, points): green when up, muted when flat or down (pair a down with an arrow, not red). */
export function deltaBand(delta: number | null | undefined, epsilon = 0.05): VerdictBand {
  return typeof delta === "number" && delta >= epsilon ? "good" : "neutral";
}

/** The semantic token each band uses; web wraps it as var(--color-*), the app reads the theme. */
export type VerdictToken = "success" | "text-secondary" | "warning" | "danger";

const TOKEN: Record<VerdictBand, VerdictToken> = {
  good: "success",
  neutral: "text-secondary",
  caution: "warning",
  bad: "danger",
};

export function bandToken(band: VerdictBand): VerdictToken {
  return TOKEN[band];
}

/** Tone names the compact summary line already uses. */
export function bandCompactTone(band: VerdictBand): "success" | "muted" | "warning" | "danger" {
  return band === "good" ? "success" : band === "caution" ? "warning" : band === "bad" ? "danger" : "muted";
}

/** Sim pages' four-step tone (neutral is the accent step). */
export function bandSimTone(band: VerdictBand): "success" | "accent" | "warning" | "danger" {
  return band === "good" ? "success" : band === "caution" ? "warning" : band === "bad" ? "danger" : "accent";
}

/** Colour tokens a server grade / verdict tone slug can map to. Never red: the product rule is no red verdicts. */
export type ToneToken = "success" | "accent" | "warning" | "muted";

/**
 * THE grade-tone -> colour token map (positive green/accent, risk amber, never red). Every grade chip (league recaps,
 * manager tendencies / "Their history", shared trades) goes through this instead of its own ladder. Danger / decline
 * words read amber here: a risk is a caution, not a red verdict.
 */
export function toneToken(tone: string | null | undefined): ToneToken {
  switch (tone) {
    case "success":
    case "accept":
      return "success";
    case "positive":
    case "accent":
    case "counter":
      return "accent";
    case "warning":
    case "risk":
    case "caution":
    case "danger":
    case "bad":
    case "negative":
    case "decline":
      return "warning";
    default:
      return "muted";
  }
}

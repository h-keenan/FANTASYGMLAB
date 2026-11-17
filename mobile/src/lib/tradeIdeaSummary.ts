/**
 * The collapsed form of a trade idea card (a CompactModule): who the partner is is the title; the summary line
 * says what the deal does, in order of what a manager scans for: the balance, the swap, how fair, how sure.
 * Pure and import-free (type only), byte-identical twin of mobile/src/lib/tradeIdeaSummary.ts. Callers pass names
 * already shortened by PlayerName's rule ("J. Surname"), so this file never truncates a name itself.
 */
import type { CompactPart } from "./compactModule";
import { bandCompactTone, deltaBand } from "./verdictTone";

export type TradeIdeaSummaryInput = {
  /** Value gain for the user (positive is good). */
  gain: number;
  sendNames: readonly string[];
  receiveNames: readonly string[];
  /** "Fair", "Slight win" ... (the value-edge band), when the server sent one. */
  band?: string | null;
  confidenceLabel?: string | null;
  realismLabel?: string | null;
};

/** "+450" / "-120" / "Even". */
export function tradeIdeaGainText(gain: number): string {
  if (gain > 0) return `+${Math.round(gain).toLocaleString("en-US")}`;
  if (gain < 0) return `-${Math.round(Math.abs(gain)).toLocaleString("en-US")}`;
  return "Even";
}

/** "J. Gibbs", "J. Gibbs + C. Olave", "J. Gibbs +2". */
export function tradeIdeaNamesText(names: readonly string[]): string {
  const clean = names.map((n) => n.trim()).filter(Boolean);
  if (clean.length === 0) return "";
  if (clean.length <= 2) return clean.join(" + ");
  return `${clean[0]} +${clean.length - 1}`;
}

/**
 * The same balance read from the user's side: "You gain +662" / "You give up 747" / "Even". A bare "-747" is ambiguous
 * (whose loss?). Colour comes from the shared deltaBand (green only for a gain; a give-up is muted, never red).
 */
export function tradeIdeaGainPhrase(gain: number): string {
  if (gain > 0) return `You gain ${tradeIdeaGainText(gain)}`;
  if (gain < 0) return `You give up ${Math.round(Math.abs(gain)).toLocaleString("en-US")}`;
  return "Even";
}

export function tradeIdeaSummaryParts(input: TradeIdeaSummaryInput): CompactPart[] {
  const send = tradeIdeaNamesText(input.sendNames);
  const receive = tradeIdeaNamesText(input.receiveNames);
  const parts: CompactPart[] = [
    {
      key: "gain",
      text: tradeIdeaGainPhrase(input.gain),
      tone: bandCompactTone(deltaBand(input.gain)),
      strong: true,
    },
  ];
  if (send && receive) parts.push({ key: "swap", text: `${send} for ${receive}` });
  else if (receive) parts.push({ key: "swap", text: `Get ${receive}` });
  else if (send) parts.push({ key: "swap", text: `Send ${send}` });
  if (input.band) parts.push({ key: "band", text: input.band, tone: "muted" });
  if (input.confidenceLabel) {
    const low = input.confidenceLabel.trim().toLowerCase() === "low";
    parts.push({ key: "confidence", text: `${input.confidenceLabel} confidence`, tone: low ? "warning" : "muted" });
  }
  return parts;
}

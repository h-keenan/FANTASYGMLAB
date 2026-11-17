/**
 * The chips on a Trade History row (import-free, byte-identical twin of mobile/src/lib/tradeOutcomeChips.ts).
 * A gain is a small green chip ("You gained +34"); a loss is a muted chip ("Down 12"), never red: a negative delta is
 * not a verdict (docs/ui-patterns.md, "Verdict colours"). Text stays neutral; colour lives only on the chip.
 */
export type TradeChipTone = "success" | "muted";
export interface TradeOutcomeChip {
  key: string;
  label: string;
  tone: TradeChipTone;
}

export function tradeOutcomeChips(input: { outcomeLabel: string; netPts: number | null; netPct: number | null }): TradeOutcomeChip[] {
  const chips: TradeOutcomeChip[] = [];
  const { netPts, netPct } = input;
  if (netPts !== null && Math.round(netPts) !== 0) {
    const n = Math.round(Math.abs(netPts));
    chips.push(netPts > 0 ? { key: "pts", label: `You gained +${n}`, tone: "success" } : { key: "pts", label: `Down ${n}`, tone: "muted" });
  } else if (netPts !== null) {
    chips.push({ key: "pts", label: "Even so far", tone: "muted" });
  } else {
    chips.push({ key: "outcome", label: input.outcomeLabel, tone: "muted" });
  }
  if (netPct !== null && Math.round(netPct) !== 0) {
    chips.push({ key: "pct", label: `${netPct > 0 ? "+" : "-"}${Math.abs(Math.round(netPct))}% value`, tone: "muted" });
  }
  return chips;
}

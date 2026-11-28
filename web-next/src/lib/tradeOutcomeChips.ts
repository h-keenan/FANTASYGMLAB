/**
 * The chips on a Trade History row (import-free, byte-identical twin of mobile/src/lib/tradeOutcomeChips.ts).
 * (Value delta, verdict badge and pick detection live here too.) A gain is a small green chip ("You gained +34"); a loss is a muted chip ("Down 12"), never red: a negative delta is
 * not a verdict (docs/ui-patterns.md, "Verdict colours"). Text stays neutral; colour lives only on the chip.
 */
export type TradeChipTone = "success" | "muted";
export interface TradeOutcomeChip {
  key: string;
  label: string;
  tone: TradeChipTone;
}

export function tradeOutcomeChips(input: { outcomeLabel: string; netPts: number | null }): TradeOutcomeChip[] {
  const chips: TradeOutcomeChip[] = [];
  const { netPts } = input;
  if (netPts !== null && Math.round(netPts) !== 0) {
    const n = Math.round(Math.abs(netPts));
    chips.push(netPts > 0 ? { key: "pts", label: `You gained +${n}`, tone: "success" } : { key: "pts", label: `Down ${n}`, tone: "muted" });
  } else if (netPts !== null) {
    chips.push({ key: "pts", label: "Even so far", tone: "muted" });
  } else {
    chips.push({ key: "outcome", label: input.outcomeLabel, tone: "muted" });
  }
  return chips;
}

/** The one value-delta number on a Trade History card ("+12%"); a loss stays neutral (never red), zero or unknown shows nothing. */
export function tradeValueDelta(netPct: number | null | undefined): { label: string; tone: TradeChipTone } | null {
  if (netPct === null || netPct === undefined || Math.round(netPct) === 0) return null;
  const n = Math.abs(Math.round(netPct));
  return netPct > 0 ? { label: `+${n}%`, tone: "success" } : { label: `-${n}%`, tone: "muted" };
}

/** The verdict badge: only a "worked out" read is green; every other read is a neutral badge, never red. */
export function tradeVerdictBadge(verdict: string | null | undefined, label: string | null | undefined): TradeOutcomeChip | null {
  const text = String(label || "").trim();
  if (!verdict || !text) return null;
  return { key: "verdict", label: text, tone: verdict === "worked_out" ? "success" : "muted" };
}

/** A draft pick asset (no tracked player id, "pick" position or a "2027 Round 1" style name) renders as a pick chip, not an avatar. */
export function isPickAsset(asset: { name?: string | null; position?: string | null; player_id?: string | null }): boolean {
  if (asset.player_id) return false;
  const pos = String(asset.position || "").toUpperCase();
  return pos === "PICK" || pos === "DP" || /\b(round|rd)\s*\d|\b\d(st|nd|rd|th)\b.*pick|\bpick\b/i.test(String(asset.name || ""));
}

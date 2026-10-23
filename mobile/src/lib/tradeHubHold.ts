// Presentation helpers for Trade Hub's hold verdict. The verdict and every
// "why" line come from the server (modules/trade_hub_engine.build_hold_verdict);
// this only decides labels and what to render. Mirrors web-next's
// TradeHubHoldCard.

export const HOLD_FACTOR_LABELS: Record<string, string> = {
  context: 'Context',
  ideas: 'Ideas',
  competition: 'Competition',
  posture: 'Posture',
};

export function holdFactorLabel(factor: string): string {
  return HOLD_FACTOR_LABELS[factor] ?? factor;
}

export interface HoldLike {
  ideas_optional?: boolean;
  why?: { factor: string; text: string }[];
}

/** Label under the hold card when ideas are still listed below it. */
export function holdIdeasNote(hold: HoldLike | null | undefined, ideaCount: number): string {
  return hold?.ideas_optional && ideaCount > 0 ? 'Ideas below are optional.' : '';
}

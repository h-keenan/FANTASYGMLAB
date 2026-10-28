import { fetchBoard } from "./publicValues";
import { mergeBoards, type TradeBoard } from "./tradeAnalyzer";

/**
 * Server-only loader for the merged public value board (1QB/Superflex x
 * with/without tight-end premium). Shared by GET /api/public-trade-values and
 * the per-link OG image route, so both read the same daily-cached numbers.
 * Throws when the base boards are unavailable; the TEP boards are optional.
 */
export async function loadTradeBoard(): Promise<TradeBoard> {
  const [std1qb, stdSf, tep1qb, tepSf] = await Promise.all([
    fetchBoard("1qb"),
    fetchBoard("superflex"),
    fetchBoard("1qb", true).catch(() => null),
    fetchBoard("superflex", true).catch(() => null),
  ]);
  return mergeBoards({ std1qb, stdSf, tep1qb, tepSf });
}

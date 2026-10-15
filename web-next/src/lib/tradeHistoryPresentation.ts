import type { PastTradeOutcome, TradeAsset, TradeOutcomeAssetSummary, TradeOutcomeResultSummary } from "@/lib/api";

/**
 * Trade History (Revision 18) presentation helpers — mirrors
 * modules/trade_outcomes_page.py's OUTCOME_LABELS/OUTCOME_BADGE_VARIANT/
 * VERDICT_BADGE_VARIANT/_verdict_detail_text and mobile's
 * TradeHistoryScreen.tsx's OUTCOME_LABEL/verdictDetailText, verbatim — same
 * two labels, same rounding, same separator on both existing surfaces.
 *
 * Deliberately its own file rather than folded into leagueRecapsPresentation
 * (Revision 13's letter-grade tone helper): League Recaps/History grades
 * EVERY trade/waiver (including still-pending ones) on an A-F letter scale;
 * Trade History only grades trades the user confirmed actually happened,
 * using a completely different four-value verdict enum computed from real
 * production + value trend after a multi-week delay. Genuinely different
 * taxonomies (see modules/trade_outcomes_page.py's own module docstring),
 * so this follows coridian_'s "don't force a shared helper" guidance rather
 * than reusing gradeToneColorVar for an enum it was never built to cover.
 */

export const OUTCOME_LABELS: Record<PastTradeOutcome["outcome"], string> = {
  yes: "Made it",
  no: "Didn't make it",
  didnt_send: "Didn't send",
};

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABELS[outcome as PastTradeOutcome["outcome"]] ?? outcome;
}

/** yes -> success, no/didnt_send -> neutral — same mapping as
 * modules/trade_outcomes_page.py's OUTCOME_BADGE_VARIANT. */
export function outcomeToneColorVar(outcome: string): string {
  return outcome === "yes" ? "var(--color-success)" : "var(--color-text-secondary)";
}

/** worked_out -> success, didnt_pan_out -> danger, mixed -> premium,
 * neutral -> secondary text — same mapping as
 * modules/trade_outcomes_page.py's VERDICT_BADGE_VARIANT (where "mixed"
 * is the "premium" badge variant) and mobile's verdictTone. */
export function verdictToneColorVar(verdict: string | null | undefined): string {
  if (verdict === "worked_out") return "var(--color-success)";
  if (verdict === "didnt_pan_out") return "var(--color-danger)";
  if (verdict === "mixed") return "var(--color-premium)";
  return "var(--color-text-secondary)";
}

/** Mirrors mobile/src/screens/TradeHistoryScreen.tsx's verdictDetailText and
 * modules/trade_outcomes_page.py's _verdict_detail_text exactly — same two
 * signals, same rounding, same " · " separator. */
export function verdictDetailText(result: TradeOutcomeResultSummary | null): string {
  if (!result) return "";
  const parts: string[] = [];
  if (result.production) {
    const avg = result.production.avg_net_per_week;
    const sign = avg > 0 ? "+" : "";
    parts.push(`${sign}${avg.toFixed(1)} PPR pts/wk edge since the trade`);
  }
  if (result.value) {
    const net = result.value.net_delta_pct;
    const sign = net > 0 ? "+" : "";
    parts.push(`${sign}${net.toFixed(0)}% value trend edge`);
  }
  return parts.join(" · ");
}

export function formatTradeHistoryDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Every trade_outcomes asset is a real tracked player, never a draft pick
 * (picks are filtered out before a trade share is ever recorded — see
 * mobile/src/components/TradeSharePreviewModal.tsx), so this always maps to
 * asset_type: "player" — reusing TradeAssetExchange's ExchangeSide/
 * TradeAssetRow (the shared give/get row this app already renders on Trade
 * Hub, GM Plan, and Live Draft) instead of a new player-identity row shape. */
export function toTradeAssets(assets: TradeOutcomeAssetSummary[]): TradeAsset[] {
  return assets.map((asset) => ({
    asset_type: "player" as const,
    player_id: asset.player_id || undefined,
    name: asset.name,
    position: asset.position,
    score: asset.value_score ?? null,
  }));
}

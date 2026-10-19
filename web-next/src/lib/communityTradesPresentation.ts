import type { CommunityTradeAsset, TradeAsset } from "@/lib/api";

/**
 * Community Trade Feed (Social/community layer, docs/roadmap.md)
 * presentation helpers. Deliberately thin — verdictDetailText/
 * verdictToneColorVar (tradeHistoryPresentation.ts) already cover the
 * verdict badge/detail text, and CommunityTradeAsset is shape-identical to
 * TradeOutcomeAssetSummary, so toTradeAssets-equivalent mapping is the only
 * thing this file adds that isn't a straight re-export.
 */

export function toCommunityTradeAssets(assets: CommunityTradeAsset[]): TradeAsset[] {
  return assets.map((asset) => ({
    asset_type: "player" as const,
    player_id: asset.player_id || undefined,
    name: asset.name,
    position: asset.position,
    score: asset.value_score ?? null,
  }));
}

export function formatCommunityTradeDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

import type { RankedPlayer, TradeIdea } from "@/lib/api";

/** Test-only TradeIdea/RankedPlayer shapes for the share-card tests. */
export const fixtureIdea: TradeIdea = {
  partner_team_name: "Rival GM",
  partner_team_avatar_url: "https://sleepercdn.com/avatars/abc",
  rationale: "",
  trade_gain: 274,
  confidence_label: "Low",
  market_realism_label: "Likely",
  reasoning_tags: [],
  category: "",
  value_edge_band: "Fair",
  impact_tag: "",
  landed_gm_target_player_ids: [],
  send_score: 3760,
  receive_score: 4034,
  recommendation_id: "rec-1",
  package: {
    value_edge: "+274",
    confidence: "Low",
    send: [{ asset_type: "player", player_id: "1", name: "Sent Player", position: "QB", team: "ARI", age: 32, score: 3760, tier: "Starter", overall_rating: 61 }],
    receive: [
      { asset_type: "player", player_id: "2", name: "Got Player", position: "WR", team: "LV", age: 26, score: 3200, tier: "Contributor", overall_rating: 72 },
      { asset_type: "pick", label: "2027 Round 3", season: "2027", round: "3", score: 834 },
    ],
  },
};

export const fixturePlayer: RankedPlayer = {
  player_id: "2",
  name: "Got Player",
  position: "WR",
  team: "LV",
  age: 26,
  status: "Active",
  injury_status: null,
  tier: "Contributor",
  score: 3200,
  overall_rank: 88,
  position_rank: 34,
  rank_unavailable_reason: null,
  opportunity_label: "Strong Opportunity",
  overall_rating: 72,
};

export function pngSize(png: ArrayBuffer): { width: number; height: number; isPng: boolean } {
  const bytes = new Uint8Array(png);
  const isPng = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every((value, index) => bytes[index] === value);
  const view = new DataView(png);
  return { width: view.getUint32(16), height: view.getUint32(20), isPng };
}

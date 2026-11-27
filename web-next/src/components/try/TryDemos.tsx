"use client";

import { SuggestedMoves } from "@/components/MatchupContent";
import { PublicTradeAnalyzer, type TradePreset } from "@/components/seo/PublicTradeAnalyzer";
import { WaiversContent } from "@/components/WaiversContent";
import { SAMPLE_START_SIT_MATCHUP, SAMPLE_WAIVERS, TRY_LEAGUE_NAME } from "@/lib/sampleTryData";

/** A realistic dynasty 2-for-1 consolidation, resolved by name against the live value board. */
export const TRY_TRADE_PRESET: TradePreset = {
  send: ["Garrett Wilson", "Travis Etienne"],
  get: ["Ja'Marr Chase"],
  format: "1qb",
};

/** The real "Suggested Moves" module (start X over Y, with the typical-week range) on one example move. */
export function StartSitDemo() {
  return <SuggestedMoves matchup={SAMPLE_START_SIT_MATCHUP} />;
}

/** The real waiver board on example data. */
export function WaiversDemo() {
  return <WaiversContent leagueName={TRY_LEAGUE_NAME} data={SAMPLE_WAIVERS} />;
}

/** The real public trade analyzer with the preset trade loaded. */
export function TradeDemo() {
  return <PublicTradeAnalyzer preset={TRY_TRADE_PRESET} />;
}

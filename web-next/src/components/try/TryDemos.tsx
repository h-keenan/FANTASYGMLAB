"use client";

import { SuggestedMoves } from "@/components/MatchupContent";
import { PublicTradeAnalyzer, type TradePreset } from "@/components/seo/PublicTradeAnalyzer";
import { WaiversContent } from "@/components/WaiversContent";
import { realStartSitMatchup, realWaiversResponse, type RealStartSit, type RealWaiverAdd } from "@/lib/tryExamples";
import { SAMPLE_START_SIT_MATCHUP, SAMPLE_WAIVERS, TRY_LEAGUE_NAME } from "@/lib/sampleTryData";

/** A realistic dynasty 2-for-1 consolidation, resolved by name against the live value board. */
export const TRY_TRADE_PRESET: TradePreset = {
  send: ["Garrett Wilson", "Travis Etienne"],
  get: ["Ja'Marr Chase"],
  format: "1qb",
};

/** The real "Suggested Moves" module (start X over Y, with the typical-week range) on one example move. */
export function StartSitDemo({ real }: { real?: RealStartSit | null }) {
  if (!real) return <SuggestedMoves matchup={SAMPLE_START_SIT_MATCHUP} />;
  return (
    <div className="flex flex-col gap-3">
      <SuggestedMoves matchup={realStartSitMatchup(real)} />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="try-matchup-note">
        {real.matchup_note}
      </p>
    </div>
  );
}

/** The real waiver board on example data. */
export function WaiversDemo({ real }: { real?: RealWaiverAdd[] | null }) {
  if (!real) return <WaiversContent leagueName={TRY_LEAGUE_NAME} data={SAMPLE_WAIVERS} />;
  return <WaiversContent leagueName="This week's trending adds" data={realWaiversResponse(real)} />;
}

/** The real public trade analyzer with the preset trade loaded. */
export function TradeDemo() {
  return <PublicTradeAnalyzer preset={TRY_TRADE_PRESET} />;
}

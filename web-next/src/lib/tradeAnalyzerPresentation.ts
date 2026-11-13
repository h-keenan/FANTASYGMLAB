/**
 * Trade Analyzer-specific presentation helpers — the manual "evaluate an
 * offer you received" builder (modules/trade_analyzer_ui.py +
 * modules/trade_offer_analyzer.py), distinct from Trade Hub's auto-generated
 * ideas (lib/tradeHubPresentation.ts, Revision 3) and from Trade Finder
 * (still Streamlit-only). The confidence-ring mapping below is NOT
 * duplicated from tradeHubPresentation.ts: modules/trade_offer_analyzer.py's
 * three confidence strings ("High confidence" / "Moderate confidence" /
 * "Close call") and modules/trade_hub_engine.py's ("High" / "Medium" / "Low"
 * + "Close call") both resolve through the exact same
 * modules/trade_visual_language.py confidence_level/confidence_ring_percent
 * functions server-side, so this page imports that module's existing port
 * rather than re-deriving a second, maybe-drifting copy.
 */

import type { DraftPickAsset, RankedPlayer, TradeAsset } from "./api";
import { notReadyReasonMessage } from "./notReadyMessages";
import { conditionsFor, itemKey, type SheetItem } from "./tradeSheetPicker";

export const ALL_TEAMS_ID = "__all__";
export const POSITION_FILTERS = ["QB", "RB", "WR", "TE", "K", "DEF"];
export const ALL_POSITION_OPTIONS = ["ALL", ...POSITION_FILTERS];

/** Same three league-link / empty-roster `reason` values every other
 * roster-scoped page gates on (see lib/notReadyMessages.ts's own docstring),
 * reworded for Trade Analyzer's framing. */
export function tradeAnalyzerReasonMessage(reason: string): string | null {
  return notReadyReasonMessage(reason, {
    linkAccount:
      "Link your Sleeper account and join this league from Home before evaluating a trade.",
    emptyRoster: "Your roster in this league looks empty, so there's nothing to trade from yet.",
  });
}

/** The additional `reason` values only POST .../trade-analyzer can return
 * (modules.mobile_api_service.post_trade_analyzer), on top of the three
 * league-link reasons tradeAnalyzerReasonMessage already covers — mirrors
 * mobile's TradeAnalyzerScreen.tsx NOT_READY_MESSAGES map. */
const ANALYZE_FAILURE_MESSAGES: Record<string, string> = {
  no_player_data: "Player data isn't available right now — try again in a bit.",
  assets_not_found: "One of the selected assets could not be resolved. Remove it and try again.",
  assets_unresolved:
    "Some players or picks in this package could not be found, so no verdict was given (a verdict on part of a trade would be misleading). Remove them and try again. This did not use one of your free evaluations.",
  fit_unavailable: "Couldn't score this package against your roster. Try again in a bit.",
};

export function analyzeFailureMessage(reason: string): string {
  return (
    tradeAnalyzerReasonMessage(reason) ??
    ANALYZE_FAILURE_MESSAGES[reason] ??
    "Could not analyze this trade."
  );
}

export function playerToTradeAsset(player: RankedPlayer): TradeAsset {
  return {
    asset_type: "player",
    player_id: player.player_id,
    name: player.name ?? "",
    position: player.position ?? "",
    team: player.team ?? "",
    age: player.age,
    score: player.score,
    injury_status: player.injury_status ?? "",
    tier: player.tier ?? "",
    overall_rating: player.overall_rating ?? null,
  };
}

export function pickToTradeAsset(pick: DraftPickAsset): TradeAsset {
  return {
    asset_type: "pick",
    label: pick.label ?? "",
    score: pick.score,
    season: pick.season != null ? String(pick.season) : undefined,
    round: pick.round != null ? String(pick.round) : undefined,
    projected_range: pick.projected_pick_range ?? undefined,
    owner_team_name: pick.owner_team_name ?? undefined,
  };
}

/** Score -> the plain-English direction line. Re-exported from the shared
 * band table (generated from modules/trade_value_bands.py): the server already
 * sends `value_summary` on the verdict, and this is the same ladder the
 * verdict itself is decided on, so a fallback can never disagree with it. */
export { valueDirectionLabel } from "./tradeValueBands.generated";

/** A ranked player as a sheet-picker item (the picker's generic shape; `ref` hands the player back). */
export function playerToSheetItem(player: RankedPlayer): SheetItem<RankedPlayer> {
  return {
    key: itemKey("player", player.player_id),
    kind: "player",
    id: player.player_id,
    label: player.name ?? "Player",
    position: player.position,
    team: player.team,
    age: player.age,
    value: player.score,
    conditions: conditionsFor({ injuryStatus: player.injury_status, status: player.status, age: player.age }),
    photoId: player.player_id,
    tier: player.tier,
    injury: player.injury_status,
    ref: player,
  };
}

/** A draft pick as a sheet-picker item, grouped by season. */
export function pickToSheetItem(pick: DraftPickAsset): SheetItem<DraftPickAsset> {
  return {
    key: itemKey("pick", pick.pick_id),
    kind: "pick",
    id: pick.pick_id,
    label: pick.label ?? "Draft pick",
    position: null,
    team: null,
    age: null,
    value: pick.score,
    conditions: [],
    detail: [pick.projected_pick_range, pick.owner_team_name].filter(Boolean).join(" · ") || null,
    group: pick.season != null ? `${pick.season} picks` : null,
    round: pick.round,
    ref: pick,
  };
}

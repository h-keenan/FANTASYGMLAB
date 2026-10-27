/**
 * Public Trade Analyzer share helpers: the per-link OG image data and the
 * UTM-tagged share link. Everything here is derived from the anonymous public
 * value board plus the ?a=&b=&f=&tep= ids in the URL: no roster, league or
 * account value ever reaches a shared image.
 */
import type { TradeAsset, TradeIdea } from "@/lib/api";
import type { TradePitch } from "@/lib/shareCard/tradeCard";

import { absoluteUrl } from "./site";
import {
  buildTradeSearch,
  evaluateTrade,
  valueOf,
  type TradeBoard,
  type TradeBoardPlayer,
  type TradeSettings,
  type TradeUrlState,
} from "./tradeAnalyzer";

export const PUBLIC_TRADE_CARD_PATH = "/share-card/public-trade";

/** UTM tokens for a link the user copies from the analyzer (lib/attribution.ts:
 * [a-z0-9_.-]). An earlier first touch is never overwritten. */
export const SHARE_LINK_UTM = {
  utm_source: "share",
  utm_medium: "copy_link",
  utm_campaign: "public_trade_analyzer",
} as const;

function toAsset(player: TradeBoardPlayer, settings: TradeSettings): TradeAsset {
  return {
    asset_type: "player",
    player_id: player.id,
    name: player.name,
    position: player.pos,
    team: player.team ?? undefined,
    age: player.age,
    score: valueOf(player, settings),
    injury_status: player.inj ?? undefined,
  };
}

/** The ids in `state` that exist on `board`, in order. */
function resolveSide(ids: readonly string[], board: TradeBoard): TradeBoardPlayer[] {
  const byId = new Map(board.players.map((p) => [p.id, p]));
  return ids.map((id) => byId.get(id)).filter((p): p is TradeBoardPlayer => Boolean(p));
}

/**
 * The share-card inputs for an entered trade, or null when either side has no
 * player on the public board (nothing honest to draw).
 */
export function buildPublicTradeCard(
  state: TradeUrlState,
  board: TradeBoard,
): { idea: TradeIdea; pitch: TradePitch } | null {
  const settings: TradeSettings = { format: state.settings.format, tep: state.settings.tep && board.tepAvailable };
  const sideA = resolveSide(state.a, board);
  const sideB = resolveSide(state.b, board);
  if (sideA.length === 0 || sideB.length === 0) return null;
  const result = evaluateTrade(sideA, sideB, settings, board.players);
  const send = sideA.map((p) => toAsset(p, settings));
  const receive = sideB.map((p) => toAsset(p, settings));
  const formatLabel = `${settings.format === "superflex" ? "Superflex" : "1QB"}${settings.tep ? " + TE premium" : ""}`;
  const idea: TradeIdea = {
    partner_team_name: "Them",
    partner_team_avatar_url: null,
    rationale: "",
    trade_gain: result.diff,
    confidence_label: "",
    market_realism_label: "",
    reasoning_tags: [],
    category: "",
    value_edge_band: result.band,
    impact_tag: "",
    landed_gm_target_player_ids: [],
    send_score: result.totalA,
    receive_score: result.totalB,
    package: { send, receive, value_edge: result.band, confidence: "" },
  };
  const pitch: TradePitch = {
    eyebrow: "Value check",
    headline: result.headline,
    lines: [
      `${Math.round(result.totalA).toLocaleString("en-US")} sent vs ${Math.round(result.totalB).toLocaleString("en-US")} received`,
      `${formatLabel} dynasty values, no roster`,
    ],
  };
  return { idea, pitch };
}

/** Absolute URL of the per-link OG image for an entered trade, or null when a side is empty. */
export function publicTradeOgImageUrl(state: TradeUrlState): string | null {
  if (state.a.length === 0 || state.b.length === 0) return null;
  return absoluteUrl(`${PUBLIC_TRADE_CARD_PATH}${buildTradeSearch(state)}`);
}

/** The link a user copies: the current URL plus first-party UTM tokens (kept if already present). */
export function shareLinkWithUtm(href: string): string {
  const url = new URL(href);
  for (const [key, value] of Object.entries(SHARE_LINK_UTM)) {
    if (!url.searchParams.has(key)) url.searchParams.set(key, value);
  }
  return url.toString().replace(/%2C/g, ",");
}

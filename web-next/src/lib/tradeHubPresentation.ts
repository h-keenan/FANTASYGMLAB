/**
 * Trade Hub-specific presentation helpers — pure ports of small, PURE
 * composition functions from modules/trade_visual_language.py and
 * modules/trade_hub_engine.py's category/impact-tag vocabulary. No
 * valuation or recommendation logic lives here: trade_gain, confidence_label,
 * market_realism_label, category, value_edge_band, and impact_tag are all
 * already computed server-side (GET .../trade-hub) — these functions only
 * decide how to color/band an already-final value, the same tier of port
 * myTeamPresentation.ts already is for My Team.
 */

import { notReadyReasonMessage } from "./notReadyMessages";
import type { RecordTradeShareAsset, RecordTradeShareBody, TradeAsset, TradeIdea } from "./api";

/** Byte-for-byte port of modules/trade_visual_language.py's confidence_level. */
export function confidenceLevel(label: string | null | undefined): "high" | "medium" | "low" {
  const text = (label || "").trim().toLowerCase();
  if (text.startsWith("high") || text.includes("high confidence")) return "high";
  if (text.startsWith("low") || text.includes("low confidence")) return "low";
  if (text.startsWith("close") || text.includes("close call")) return "low";
  return "medium";
}

/** Port of confidence_ring_percent — same mapping realismRingPercent below uses. */
export function confidenceRingPercent(label: string | null | undefined): number {
  const level = confidenceLevel(label);
  if (level === "high") return 90;
  if (level === "low") return 35;
  return 60;
}

/** Byte-for-byte port of modules/trade_visual_language.py's realism_level. */
export function realismLevel(label: string | null | undefined): "high" | "medium" | "low" {
  const text = (label || "").trim().toLowerCase();
  if (text.startsWith("realistic")) return "high";
  if (text.startsWith("thin")) return "low";
  return "medium";
}

/** Port of realism_ring_percent — same 90/60/35 scale as confidence. */
export function realismRingPercent(label: string | null | undefined): number {
  const level = realismLevel(label);
  if (level === "high") return 90;
  if (level === "low") return 35;
  return 60;
}

/** Ring level -> the existing .value-ring--{low|mid|high} tone classes
 * (My Team's Team Value ring already defines these three). */
export function levelToRingTone(level: "high" | "medium" | "low"): "low" | "mid" | "high" {
  if (level === "high") return "high";
  if (level === "low") return "low";
  return "mid";
}

/** value_edge_band (already computed server-side by
 * modules.trade_visual_language.trade_value_band) -> the fairness-pill tone,
 * ported from modules/trade_hub_ui.py's _TRADE_FAIRNESS_BAND_TONE. Decoupled
 * from the raw trade_gain sign so a marginally-positive "Fair" trade doesn't
 * read as success-green and a marginally-negative "Slight Overpay" doesn't
 * read as danger-red. */
const FAIRNESS_BAND_TONE: Record<string, string> = {
  favorable: "var(--color-success)",
  fair: "var(--color-text-secondary)",
  "slight overpay": "var(--color-warning)",
  "major overpay": "var(--color-danger)",
};

export function fairnessBandColor(band: string | null | undefined): string {
  return FAIRNESS_BAND_TONE[(band || "").trim().toLowerCase()] ?? "var(--color-text-secondary)";
}

/** trade_gain (signed int) -> the display delta string ("+150"/"-800"/"Even") —
 * port of render_trade_idea_card's own delta_text derivation. */
export function formatTradeGain(gain: number): string {
  if (gain > 0) return `+${Math.round(gain).toLocaleString()}`;
  if (gain < 0) return `-${Math.round(Math.abs(gain)).toLocaleString()}`;
  return "Even";
}

export type LeanPolarity = "pos" | "neg" | "even";

export interface LeanBar {
  polarity: LeanPolarity;
  /** 0-50, the half-track fraction value_edge_lean_bar_html's CSS consumes
   * (--tvl-lean-fraction is `fraction * 50%`, since the fill grows from the
   * center tick outward in either direction). */
  halfTrackPercent: number;
}

/** Byte-for-byte port of modules/trade_visual_language.py's
 * value_edge_lean_bar_html's fraction math: a true ratio over the real,
 * untruncated per-side totals (|receive - send| / (receive + send)), not a
 * saturating curve over the magnitude alone. */
export function leanBar(sendScore: number, receiveScore: number): LeanBar {
  const send = Math.max(0, sendScore || 0);
  const receive = Math.max(0, receiveScore || 0);
  const total = send + receive;
  const imbalance = receive - send;
  if (total <= 0 || Math.abs(imbalance) < 1e-9) {
    return { polarity: "even", halfTrackPercent: 0 };
  }
  if (imbalance > 0) {
    return { polarity: "pos", halfTrackPercent: Math.min(1, imbalance / total) * 50 };
  }
  return { polarity: "neg", halfTrackPercent: Math.min(1, Math.abs(imbalance) / total) * 50 };
}

/** modules/trade_hub_ui.py's trade_hub_display_section taxonomy, mapped to
 * this app's existing semantic tokens (not a new color per category) — same
 * mapping mobile/src/screens/TradeHubScreen.tsx's categoryColors uses,
 * ported to web-next's CSS variables instead of React Native ThemeColors. */
const CATEGORY_COLOR_VAR: Record<string, string> = {
  "Headline Recommendation": "var(--color-accent)",
  "Health Relief": "var(--color-danger)",
  "Draft Capital": "var(--color-premium)",
  "Age Optimization": "var(--color-diagnostic)",
  Rebuild: "var(--color-diagnostic)",
  Contender: "var(--color-success)",
  "Need-Based": "var(--color-accent)",
  "High Confidence": "var(--color-success)",
};

export function categoryColor(category: string | null | undefined): string {
  return CATEGORY_COLOR_VAR[category || ""] ?? "var(--color-text-secondary)";
}

export interface ImpactTagConfig {
  label: string;
  color: string;
}

/** Port of mobile's impactTagConfig — same three server-computed impact_tag
 * values (modules.trade_hub_engine._classify_impact_tag), same labels. */
const IMPACT_TAG_CONFIG: Record<string, ImpactTagConfig> = {
  high_impact: { label: "High Impact", color: "var(--color-accent)" },
  buy_low: { label: "Buy Low", color: "var(--color-success)" },
  sell_high: { label: "Sell High", color: "var(--color-premium)" },
};

export function impactTagConfig(tag: string | null | undefined): ImpactTagConfig | null {
  if (!tag) return null;
  return IMPACT_TAG_CONFIG[tag] ?? null;
}

/** Same not-ready `reason` values GET .../trade-hub (and .../my-team) can
 * return (modules.mobile_api_service._resolve_my_roster plus "empty_roster"),
 * reworded for this page's own "no trade ideas yet" framing instead of
 * myTeamPresentation.ts's "see your lineup" copy. The shared classification
 * lives in lib/notReadyMessages.ts (consolidated there in Revision 4 out of
 * three byte-identical reason sets — see that file's own comment). */
/** modules/league_calendar.py's TRADE_DEADLINE_PASSED_MESSAGE — Trade Hub
 * and Trade Finder's reason === "trade_deadline_passed" state. */
export const TRADE_DEADLINE_PASSED_MESSAGE = "Trade deadline has passed; trades reopen after the season.";

export function tradeHubReasonMessage(reason: string): string | null {
  if (reason === "trade_deadline_passed") return TRADE_DEADLINE_PASSED_MESSAGE;
  return notReadyReasonMessage(reason, {
    linkAccount: "Link your Sleeper account and join this league from Home to see trade ideas for your roster.",
    emptyRoster: "Your roster in this league looks empty, so there's nothing to build trade ideas around yet.",
  });
}

/** modules/trade_hub_ui.py's LOW_CONFIDENCE_USER_NOTE, shown on the
 * quick-view card itself (kept visible even though the confidence ring
 * moved to the tap-through detail — coridian_, 2026-10-13) so a genuinely
 * low-confidence trade still reads as risky at a glance. */
export const LOW_CONFIDENCE_USER_NOTE = "More dependent on partner preference and market fit.";

function assetLabel(asset: TradeAsset): string {
  return asset.name || asset.label || "Unknown asset";
}

/**
 * Plain-text summary of a trade idea for the Share button (coridian_,
 * 2026-10-16: "there's no share button on the trade"). Deliberately plain
 * text rather than the shareable rendered-image card mobile's
 * TradeSharePreviewModal produces — this app has no canvas/image-rendering
 * pipeline yet, and a real text summary via the Web Share API (or a
 * clipboard-copy fallback) is a genuinely useful share today rather than a
 * half-built image generator. Never claims the trade was accepted/declined,
 * same restraint mobile's ideaToShareVerdict comment calls out.
 */
export function tradeIdeaShareText(idea: TradeIdea): string {
  const send = idea.package.send.map(assetLabel).join(", ") || "nothing";
  const receive = idea.package.receive.map(assetLabel).join(", ") || "nothing";
  return (
    `Trade idea vs. ${idea.partner_team_name} (${idea.value_edge_band || "Fair"})\n` +
    `You send: ${send}\n` +
    `You get: ${receive}\n` +
    `Balance: ${formatTradeGain(idea.trade_gain)}`
  );
}

function shareRecordAsset(asset: TradeAsset): RecordTradeShareAsset {
  return {
    name: asset.name ?? "Unknown",
    position: asset.position ?? "",
    player_id: asset.player_id || undefined,
    value_score: asset.score ?? undefined,
  };
}

/**
 * The POST /v1/leagues/{id}/trade-outcomes body for a shared Trade Hub or
 * Trade Finder idea. Mirrors mobile exactly (TradeHubScreen's
 * shareAssetsToPlayers + ideaToShareVerdict, then
 * TradeSharePreviewModal.recordShare): draft picks are dropped, an empty
 * player_id becomes undefined, the idea's own score is the baseline
 * value_score, and the label is the market-realism label (falling back to
 * "Trade Hub idea"). The lens is whichever one the idea was built under.
 */
export function tradeIdeaShareRecord(idea: TradeIdea, lens: string): RecordTradeShareBody {
  const players = (assets: TradeAsset[]) =>
    (assets ?? []).filter((asset) => asset.asset_type !== "pick").map(shareRecordAsset);
  return {
    partnerTeamName: idea.partner_team_name,
    send: players(idea.package.send),
    receive: players(idea.package.receive),
    valueEdgeLabel: idea.market_realism_label || "Trade Hub idea",
    valuationLens: lens,
  };
}

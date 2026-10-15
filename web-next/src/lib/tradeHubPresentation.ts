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
 * myTeamPresentation.ts's "see your lineup" copy. */
const NO_LEAGUE_REASONS = new Set([
  "no_sleeper_username_linked",
  "sleeper_user_not_found",
  "not_a_member_of_league",
]);

export function tradeHubReasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see trade ideas for your roster.";
  }
  if (reason === "empty_roster") {
    return "Your roster in this league looks empty, so there's nothing to build trade ideas around yet.";
  }
  if (reason === "no_player_data") {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

/** modules/trade_hub_ui.py's LOW_CONFIDENCE_USER_NOTE, shown on the
 * quick-view card itself (kept visible even though the confidence ring
 * moved to the tap-through detail — coridian_, 2026-10-13) so a genuinely
 * low-confidence trade still reads as risky at a glance. */
export const LOW_CONFIDENCE_USER_NOTE = "More dependent on partner preference and market fit.";

import type { PlayerAward, QuickViewModel, QuickViewStatItem } from "./api";
import { metricToneBand } from "./playerPresentation";

/**
 * Presentation helpers for the shared PlayerQuickView modal (Revision 22) —
 * the web port of app.py's Player Quick View pop-up
 * (modules/player_quick_view.py), coridian_'s flagged gap: web-next shows
 * player identity everywhere via OvrGauge/PositionBadge but has no
 * tap-to-open detail popup anywhere, unlike Streamlit. These functions are
 * pure presentation (no fetching) so PlayerQuickView.tsx stays focused on
 * layout/markup.
 */

/** "1st"/"2nd"/"3rd"/"4th"... — byte-identical rule to
 * modules.player_quick_view._ordinal. */
export function ordinal(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 10 && mod100 <= 20) return `${value}th`;
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[value % 10] ?? "th";
  return `${value}${suffix}`;
}

/** Red/gold/green percentile banding for a stat row's percentile chip —
 * same thresholds as modules.player_quick_view._percentile_band, which is
 * the same 34/67 split playerPresentation.ts's metricToneBand already
 * encodes for team-level percentiles. One function, not a second copy of
 * the same thresholds. */
export const statPercentileBand = metricToneBand;

/** OVR-ring / sub-rating-chip banding on the rating's own 1-99 scale — NOT
 * the same thresholds as statPercentileBand (that bands a 1-100
 * percentile; this bands the compressed 1-99 rating the percentile curve
 * already produced). Byte-identical to
 * modules.player_quick_view._overall_rating_band. */
export function overallRatingBand(rating: number): "low" | "mid" | "high" {
  if (rating < 50) return "low";
  if (rating < 80) return "mid";
  return "high";
}

/** Display order + abbreviation for the Model tab's sub-rating chip row —
 * same "MKT 91 - OPP 84 - SCR 62 - ROLE 73 - DUR 58" row mobile's
 * SubRatingRow and app.py's sub_rating_row_html both render. */
export const SUB_RATING_DISPLAY: ReadonlyArray<{
  key: keyof Pick<
    QuickViewModel,
    "market_rating" | "opportunity_rating" | "scarcity_rating" | "role_rating" | "durability_rating"
  >;
  abbr: string;
  label: string;
}> = [
  { key: "market_rating", abbr: "MKT", label: "Market" },
  { key: "opportunity_rating", abbr: "OPP", label: "Opportunity" },
  { key: "scarcity_rating", abbr: "SCR", label: "Scarcity" },
  { key: "role_rating", abbr: "ROLE", label: "Role" },
  { key: "durability_rating", abbr: "DUR", label: "Durability" },
];

/** Groups to render for one QuickViewSeason, in display order, skipping any
 * group with no rows — mirrors the Key Stats / Fantasy / Usage / Efficiency
 * section order the Streamlit and mobile Stats tabs both use. */
export function seasonStatGroups(season: {
  key_stats: QuickViewStatItem[];
  fantasy: QuickViewStatItem[];
  usage: QuickViewStatItem[];
  efficiency: QuickViewStatItem[];
}): Array<{ title: string; items: QuickViewStatItem[] }> {
  return [
    { title: "Production", items: season.key_stats },
    { title: "Fantasy", items: season.fantasy },
    { title: "Usage", items: season.usage },
    { title: "Efficiency", items: season.efficiency },
  ].filter((group) => group.items.length > 0);
}

/** Badge tier -> a short, non-fabricated color token name, for the Awards
 * strip's gold/silver/bronze dot. */
export function awardTierTone(tier: PlayerAward["tier"]): "gold" | "silver" | "bronze" | "neutral" {
  if (tier === "gold" || tier === "silver" || tier === "bronze") return tier;
  return "neutral";
}

// coridian_, 2026-10-19 (screenshot): "this guy is a backup and the
// starting qb is hurt so he is starting but that needs to be explained and
// the contributor tag doesnt make sense if he hasnt been playing much" —
// player_tier (modules/player_tiers.py) is a long-horizon, season-long
// value read; opportunity_label (modules/rankings.opportunity_profile) is
// a right-now depth-chart read. They can legitimately disagree — a backup
// promoted this week by an injury reads "Elite Opportunity" immediately,
// while his season-long tier hasn't caught up — and showing both chips
// with no explanation reads as a contradiction, not two different time
// horizons. A real fix that reconciles the two signals belongs in the
// shared ranking engine (used by web, mobile, and Streamlit alike); this
// is the presentation-only stopgap: flag the specific combination that
// caused the confusion and say why, without changing either value.
const LOW_PLAYER_TIERS = new Set(["Contributor", "Depth", "Developmental"]);
const HIGH_OPPORTUNITY_LABELS = new Set(["Elite Opportunity", "Strong Opportunity"]);

export function tierOpportunityMismatchCaption(tier: string | null | undefined, opportunityLabel: string | null | undefined): string | null {
  if (!tier || !opportunityLabel) return null;
  if (!LOW_PLAYER_TIERS.has(tier) || !HIGH_OPPORTUNITY_LABELS.has(opportunityLabel)) return null;
  return `${tier} reflects value over the full season — this role read (${opportunityLabel}) is about right now, and can jump ahead of it fast (e.g. an injury-driven promotion).`;
}

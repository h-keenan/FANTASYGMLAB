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

/** Up to two initials from a player's display name — the same fallback
 * avatar_html uses when no headshot is available. web-next has no headshot
 * CDN wiring yet (unlike mobile's cached_headshot_data_url), so the modal's
 * portrait is always this initials badge, not a photo. */
export function playerInitials(name: string | null | undefined): string {
  const trimmed = (name ?? "").trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/).filter(Boolean);
  const initials = parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return initials || "?";
}

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

/**
 * Canonical player-tier ladder -> the `--color-tier-*` CSS variable it
 * renders with. Byte-for-byte port of mobile's playerTier.ts tier ids and
 * the stored-tier normalization table (mobile/src/lib/playerTier.ts) so this
 * app shows the same seven-tier "prestige" ladder and the same stored-tier
 * synonyms mobile already resolves. Returns a CSS variable name (not a raw
 * hex) since this app's dark/light swap is handled by globals.css's
 * `@media (prefers-color-scheme: light)` block, unlike mobile's explicit
 * `isDark` branch — one definition per tier instead of two.
 *
 * Deliberately a separate token family from the pre-existing
 * `--color-prestige-*` CSS variables (globals.css) — those predate this
 * ladder (six tiers including a "replacement" tier that doesn't exist here,
 * stale pre-color-audit hex values) and the one live consumer
 * (leagueRecapsPresentation's category tint) means something unrelated to a
 * player's tier. Reusing or renaming them would either collide with that
 * category-color usage or silently change its value.
 */

export type PlayerTierId =
  | "generational"
  | "elite"
  | "impact_starter"
  | "starter"
  | "contributor"
  | "committee_role"
  | "depth_developmental";

export interface PlayerTierIdentity {
  tierId: PlayerTierId;
  semanticLabel: string;
  shortLabel: string;
  colorVar: string;
}

export const PLAYER_TIER_LADDER: PlayerTierIdentity[] = [
  { tierId: "generational", semanticLabel: "Generational", shortLabel: "GENERATIONAL", colorVar: "--color-tier-generational" },
  { tierId: "elite", semanticLabel: "Elite", shortLabel: "ELITE", colorVar: "--color-tier-elite" },
  { tierId: "impact_starter", semanticLabel: "Impact Starter", shortLabel: "IMPACT STARTER", colorVar: "--color-tier-impact-starter" },
  { tierId: "starter", semanticLabel: "Starter", shortLabel: "STARTER", colorVar: "--color-tier-starter" },
  { tierId: "contributor", semanticLabel: "Contributor", shortLabel: "CONTRIBUTOR", colorVar: "--color-tier-contributor" },
  { tierId: "committee_role", semanticLabel: "Committee / Role", shortLabel: "COMMITTEE/ROLE", colorVar: "--color-tier-committee-role" },
  { tierId: "depth_developmental", semanticLabel: "Depth / Developmental", shortLabel: "DEPTH/DEV", colorVar: "--color-tier-depth-developmental" },
];

const DEFAULT_TIER = PLAYER_TIER_LADDER[6];
const TIER_BY_ID = new Map(PLAYER_TIER_LADDER.map((tier) => [tier.tierId, tier]));

export type TierGlowIntensity = "strong" | "medium" | "subtle" | null;

// coridian_, 2026-10-19 (queued cosmetic, lowest priority): "an effect
// around the prestige ring ... different for different tiers. Obviously
// lower tiers don't need one." Only the top three tiers glow at all —
// everyone from `starter` down keeps the plain ring unchanged, same as
// today.
const GLOW_INTENSITY_BY_TIER: Record<PlayerTierId, TierGlowIntensity> = {
  generational: "strong",
  elite: "medium",
  impact_starter: "subtle",
  starter: null,
  contributor: null,
  committee_role: null,
  depth_developmental: null,
};

export function tierGlowIntensity(tierId: PlayerTierId): TierGlowIntensity {
  return GLOW_INTENSITY_BY_TIER[tierId];
}

// Verbatim copy of mobile's STORED_TIER_TO_ID synonym table.
const STORED_TIER_TO_ID: Record<string, PlayerTierId> = {
  elite: "generational",
  star: "elite",
  "core starter": "impact_starter",
  core_starter: "impact_starter",
  starter: "starter",
  contributor: "contributor",
  depth: "committee_role",
  developmental: "depth_developmental",
  development: "depth_developmental",
  generational: "generational",
  "impact starter": "impact_starter",
  impact_starter: "impact_starter",
  "committee / role": "committee_role",
  "committee / role player": "committee_role",
  committee: "committee_role",
  "role player": "committee_role",
  "depth / developmental": "depth_developmental",
  "elite contributor": "elite",
};

// Workload/opportunity labels (e.g. "Committee Back") sometimes land in the
// same stored-tier field on a thin pool — these aren't tiers at all, so they
// fall through to the default rather than mis-mapping onto a real tier.
const ROLE_OPPORTUNITY_LABELS = new Set([
  "committee back",
  "backup with upside",
  "workhorse",
  "elite opportunity",
  "strong opportunity",
  "starter at risk",
  "opportunity unclear",
]);

function normalize(value: string | null | undefined): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/** Plain-text name for a stored tier ("Elite" -> "Generational"), or null when the
 * string is not a tier name. The one place text labels come from on this side;
 * mirrors modules/player_tier_identity.tier_display_label. */
export function tierTextLabel(storedTier: string | null | undefined): string | null {
  const key = normalize(storedTier);
  if (!key || ROLE_OPPORTUNITY_LABELS.has(key)) return null;
  const id = STORED_TIER_TO_ID[key];
  return id ? (TIER_BY_ID.get(id as PlayerTierId)?.semanticLabel ?? null) : null;
}

export function resolvePlayerTier(storedTier: string | null | undefined): PlayerTierIdentity {
  const key = normalize(storedTier);
  if (!key || ROLE_OPPORTUNITY_LABELS.has(key)) return DEFAULT_TIER;
  return TIER_BY_ID.get(STORED_TIER_TO_ID[key]) ?? DEFAULT_TIER;
}

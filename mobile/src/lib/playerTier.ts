/**
 * Canonical player-tier ladder — ported from modules/player_tier_identity.py
 * so mobile shows the same "prestige level" language and colors as the web
 * app (Elite, Contributor, etc.), not a re-invented label set. Presentation
 * mapping only: never changes valuation, ranks, or the underlying score.
 */

export interface PlayerTierIdentity {
  tierId: string;
  semanticLabel: string;
  shortLabel: string;
  abbrLabel: string;
  rankOrder: number;
  color: string;
}

export const PLAYER_TIER_LADDER: PlayerTierIdentity[] = [
  { tierId: 'generational', semanticLabel: 'Generational', shortLabel: 'GENERATIONAL', abbrLabel: 'GEN', rankOrder: 1, color: '#67E8F9' },
  { tierId: 'elite', semanticLabel: 'Elite', shortLabel: 'ELITE', abbrLabel: 'ELITE', rankOrder: 2, color: '#8B93FF' },
  { tierId: 'impact_starter', semanticLabel: 'Impact Starter', shortLabel: 'IMPACT STARTER', abbrLabel: 'IMPACT', rankOrder: 3, color: '#EF4444' },
  { tierId: 'starter', semanticLabel: 'Starter', shortLabel: 'STARTER', abbrLabel: 'STARTER', rankOrder: 4, color: '#D8B85A' },
  { tierId: 'contributor', semanticLabel: 'Contributor', shortLabel: 'CONTRIBUTOR', abbrLabel: 'CONTRIB', rankOrder: 5, color: '#D7DBE2' },
  { tierId: 'committee_role', semanticLabel: 'Committee / Role', shortLabel: 'COMMITTEE/ROLE', abbrLabel: 'COMMITTEE', rankOrder: 6, color: '#F59E0B' },
  { tierId: 'depth_developmental', semanticLabel: 'Depth / Developmental', shortLabel: 'DEPTH/DEV', abbrLabel: 'DEPTH', rankOrder: 7, color: '#626A75' },
];

// coridian_ (2026-09-22): "a lot of the colored aspects blend in" on light
// mode. The ladder above was tuned entirely for a near-black backdrop —
// `contributor`'s #D7DBE2 is nearly white, unreadable on a light card, and
// several others are too pale to hold their own hue against glacier-white.
// Same tier identities, colors pushed dark/saturated enough to read on a
// light surface. Keyed by tierId so PLAYER_TIER_LADDER's own order/labels
// stay the single source of truth for everything except color.
const TIER_COLOR_LIGHT: Record<string, string> = {
  generational: '#0E7490',
  elite: '#4338CA',
  impact_starter: '#B91C1C',
  starter: '#854D0E',
  contributor: '#475569',
  committee_role: '#C2410C',
  depth_developmental: '#52525B',
};

const DEFAULT_TIER = PLAYER_TIER_LADDER[6];

const STORED_TIER_TO_ID: Record<string, string> = {
  elite: 'generational',
  star: 'elite',
  'core starter': 'impact_starter',
  core_starter: 'impact_starter',
  starter: 'starter',
  contributor: 'contributor',
  depth: 'committee_role',
  developmental: 'depth_developmental',
  development: 'depth_developmental',
  generational: 'generational',
  'impact starter': 'impact_starter',
  impact_starter: 'impact_starter',
  'committee / role': 'committee_role',
  'committee / role player': 'committee_role',
  committee: 'committee_role',
  'role player': 'committee_role',
  'depth / developmental': 'depth_developmental',
  'elite contributor': 'elite',
};

const ROLE_OPPORTUNITY_LABELS = new Set([
  'committee back',
  'backup with upside',
  'workhorse',
  'elite opportunity',
  'strong opportunity',
  'starter at risk',
  'opportunity unclear',
]);

const TIER_BY_ID = new Map(PLAYER_TIER_LADDER.map((tier) => [tier.tierId, tier]));

function normalize(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase().replace(/_/g, ' ').split(/\s+/).filter(Boolean).join(' ');
}

export function resolvePlayerTier(storedTier: string | null | undefined, isDark = true): PlayerTierIdentity {
  const key = normalize(storedTier);
  const base =
    !key || ROLE_OPPORTUNITY_LABELS.has(key)
      ? DEFAULT_TIER
      : TIER_BY_ID.get(STORED_TIER_TO_ID[key]) ?? DEFAULT_TIER;
  if (isDark) return base;
  return { ...base, color: TIER_COLOR_LIGHT[base.tierId] ?? base.color };
}

/** Black or white, whichever reads on a solid fill of this color — the
 * tier ladder spans light cyans/grays through dark slate, so a single
 * hardcoded text color washes out on half of them. Used for the
 * high-emphasis solid-fill tier pill (Player Detail hero); the dense-list
 * TierBadge chip stays translucent-on-dark and doesn't need this. */
export function contrastTextColor(hex: string): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? '#0D1117' : '#F2F4F7';
}

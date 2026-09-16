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

export function resolvePlayerTier(storedTier: string | null | undefined): PlayerTierIdentity {
  const key = normalize(storedTier);
  if (!key || ROLE_OPPORTUNITY_LABELS.has(key)) return DEFAULT_TIER;
  const mappedId = STORED_TIER_TO_ID[key];
  if (!mappedId) return DEFAULT_TIER;
  return TIER_BY_ID.get(mappedId) ?? DEFAULT_TIER;
}

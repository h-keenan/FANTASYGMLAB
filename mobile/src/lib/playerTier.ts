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

// Color-system audit (2026-10-03, playerTier follow-up): five of these dark
// values were re-hued off collisions flagged against theme.ts tokens and
// against each other — see the per-tier comments below for the contrast
// math and hue-distance reasoning behind each replacement. `contributor` and
// `depth_developmental` are untouched; they were never part of a collision.
export const PLAYER_TIER_LADDER: PlayerTierIdentity[] = [
  // `generational` was #67E8F9 — only ~24deg of hue from theme.ts's
  // `accent`/`accentSoft` (#00D4FF/#5CE4FF, hue 190deg) at near-identical
  // saturation/lightness, so the single most prestigious tier read as
  // "selected nav item" cyan instead of a distinct color. Re-hued to a
  // jade/teal at hue 166deg: 24deg from `accent` *and* 24deg from `success`
  // (#22C55E, hue 142deg) on the other side, so it sits in open space
  // between both rather than drifting into either. Keeps the same high
  // saturation/lightness as the old value (still reads "icy/premium" on
  // near-black) — only the hue moved. 15.46:1 against `background`,
  // 12.19:1 against `backgroundElevated`.
  { tierId: 'generational', semanticLabel: 'Generational', shortLabel: 'GENERATIONAL', abbrLabel: 'GEN', rankOrder: 1, color: '#78F2D5' },
  // `elite` was #8B93FF — byte-for-byte identical to theme.ts's `violet`
  // token (hue 236deg, "secondary analytics/informational category" per
  // the audit doc's semantic table), and only 21deg from the K position
  // color (#A78BFA, hue 255deg) the audit separately flagged as already
  // crowding that lavender-purple family. Re-hued to a royal
  // magenta/orchid at hue 300deg: 64deg clear of `violet`, 45deg clear of K,
  // 51deg clear of QB's rose (#FB7185, hue 351deg) on the other side. Reads
  // as a distinct "prestige" purple rather than either violet's
  // informational meaning or K's position color. 8.06:1 against
  // `background`, 6.36:1 against `backgroundElevated`.
  { tierId: 'elite', semanticLabel: 'Elite', shortLabel: 'ELITE', abbrLabel: 'ELT', rankOrder: 2, color: '#EF6CEF' },
  // `impact_starter` was #EF4444 — functionally the same red as theme.ts's
  // `danger` token (#FF4D4D, hue 0deg), so a positive tier-3-of-7
  // classification read as an injury/danger flag. Re-hued to a copper at
  // hue 15deg: a "related but distinct" neighbor of the TE position color
  // (#FB923C, hue 27deg) per the audit's own suggestion, while landing
  // 15deg clear of `danger` on the other side (the collision actually being
  // fixed) and 27deg clear of `premium` (#FFC43D, hue 42deg) so it doesn't
  // wander into the amber/gold lane either. 6.50:1 against `background`,
  // 5.13:1 against `backgroundElevated` (comparable to the old value's
  // 5.58:1 / 4.40:1).
  { tierId: 'impact_starter', semanticLabel: 'Impact Starter', shortLabel: 'IMPACT STARTER', abbrLabel: 'IMPACT', rankOrder: 3, color: '#F06233' },
  // `starter` was #D8B85A (hue 45deg) — in the same amber/gold lane as
  // `premium` (42deg), `committee_role` below (was 38deg), and the award
  // gold tier (51deg). Moved off that lane entirely into an olive/khaki at
  // hue 73deg: 31deg clear of `premium`, 22deg clear of award gold, and
  // 35deg clear of the re-hued `committee_role` (108deg) below. 11.25:1
  // against `background`, 8.88:1 against `backgroundElevated` (vs. the old
  // value's 10.92:1 / 8.62:1 — effectively unchanged contrast, hue only).
  { tierId: 'starter', semanticLabel: 'Starter', shortLabel: 'STARTER', abbrLabel: 'STR', rankOrder: 4, color: '#B2C766' },
  { tierId: 'contributor', semanticLabel: 'Contributor', shortLabel: 'CONTRIBUTOR', abbrLabel: 'CONTRIB', rankOrder: 5, color: '#D7DBE2' },
  // `committee_role` was #F59E0B (hue 38deg) — the same amber/gold lane as
  // `premium`, old `starter`, and award gold (the audit's "4-way gold/amber
  // cluster"). Moved to a moss/fern green at hue 108deg: 34deg clear of
  // `success` (#22C55E, hue 142deg) and the RB position color (same
  // hue/family) so it doesn't drift into the green lane either, and 35deg
  // clear of the re-hued `starter` above so the two don't just recreate a
  // new collision with each other. 9.39:1 against `background`, 7.40:1
  // against `backgroundElevated` (vs. the old value's 9.78:1 / 7.71:1).
  { tierId: 'committee_role', semanticLabel: 'Committee / Role', shortLabel: 'COMMITTEE/ROLE', abbrLabel: 'COMMITTEE', rankOrder: 6, color: '#51C534' },
  { tierId: 'depth_developmental', semanticLabel: 'Depth / Developmental', shortLabel: 'DEPTH/DEV', abbrLabel: 'DEPTH', rankOrder: 7, color: '#626A75' },
];

// coridian_ (2026-09-22): "a lot of the colored aspects blend in" on light
// mode. The ladder above was tuned entirely for a near-black backdrop —
// `contributor`'s #D7DBE2 is nearly white, unreadable on a light card, and
// several others are too pale to hold their own hue against glacier-white.
// Same tier identities, colors pushed dark/saturated enough to read on a
// light surface. Keyed by tierId so PLAYER_TIER_LADDER's own order/labels
// stay the single source of truth for everything except color.
//
// Color-system audit (2026-10-03, playerTier follow-up): generational,
// elite, impact_starter, starter, and committee_role below were re-hued to
// the same new hue families as their dark counterparts above (each
// comment there has the hue-distance math); these light values are just
// that same hue darkened/saturated enough to clear AA on a white/glacier
// card, the same treatment this file already applied in the block above.
const TIER_COLOR_LIGHT: Record<string, string> = {
  // hue 172deg (dark counterpart is 166deg; light-mode saturation/lightness
  // retuning shifts the rendered hue slightly, same as every other pair in
  // this file). 4.47:1 against `background`, 5.03:1 against `surface` (old
  // value: 4.76:1 / 5.36:1).
  generational: '#0C7D6E',
  // hue 300deg, matching the dark value exactly (only lightness/saturation
  // differ between the two, as with every tier below). 5.74:1 against
  // `background`, 6.46:1 against `surface` (old value: 7.03:1 / 7.90:1).
  elite: '#972697',
  // hue 11deg — copper, 11deg from `danger_light` (#D92D2D, hue 0deg), 6deg
  // from TE_light (#C2410C, hue 17deg) as its "related neighbor," same
  // reasoning as the dark value. 5.78:1 against `background`, 6.50:1
  // against `surface` (old value: 5.75:1 / 6.47:1 — contrast preserved,
  // hue moved off red).
  impact_starter: '#AE3013',
  // hue 74deg olive, off the amber lane shared by `premium`/old
  // `committee_role`/award gold. 4.93:1 against `background`, 5.54:1
  // against `surface` (old value: 6.09:1 / 6.85:1).
  starter: '#5C701A',
  contributor: '#475569',
  // hue 108deg moss green, 34deg clear of `success_light` (#178A43, hue
  // 143deg). 5.44:1 against `background`, 6.11:1 against `surface` (old
  // value: 4.60:1 / 5.18:1).
  committee_role: '#2B701A',
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

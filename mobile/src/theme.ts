import { Platform } from 'react-native';

/**
 * Shared design tokens — colors, spacing, radii, shadows, and motion
 * constants. Kept deliberately small: this is a client-side presentation
 * layer only, it doesn't encode any product/valuation logic.
 *
 * Palette matches the FGL brand style sheet (blue-black canvas, #151B22
 * cards, #00D4FF/#FFC43D/#FF4D4D trajectory colors) rather than the web
 * app's own flat/dossier CSS tokens — the brand sheet is the newer,
 * explicitly-approved source of truth for how the *mobile app* should look
 * (deliberate divergence from modules/design_tokens.py, which the web app
 * still uses as-is).
 */

export const colors = {
  background: '#0D1117',
  backgroundElevated: '#1E2631',
  surface: '#151B22',
  surfaceSolid: '#151B22',
  border: '#1E2631',
  borderStrong: '#2A3441',
  hairline: 'rgba(255,255,255,0.08)',
  textPrimary: '#F2F4F7',
  textSecondary: '#A6B0BB',
  textTertiary: '#6F7A87',
  accent: '#00D4FF',
  accentSoft: '#5CE4FF',
  accentMuted: 'rgba(0,212,255,0.14)',
  danger: '#FF4D4D',
  dangerMuted: 'rgba(255,77,77,0.14)',
  success: '#22C55E',
  successBright: '#4ADE80',
  successMuted: 'rgba(34,197,94,0.14)',
  premium: '#FFC43D',
  premiumMuted: 'rgba(255,196,61,0.14)',
  badgeBackground: 'rgba(0,212,255,0.14)',
  badgeText: '#5CE4FF',
  violet: '#8B93FF',
};

/**
 * Position identity — byte-identical to modules/design_tokens.py's
 * --color-position-* tokens (unlike the rest of `colors` above, which is a
 * deliberate brand-sheet divergence from web's palette, position colors
 * were simply never ported at all — confirmed by direct grep, every screen
 * rendered position as plain secondary-color text). Chip/accent only, per
 * design_tokens.py's own comment: never recolor the whole player card.
 */
// Matched to Sleeper's own position colors (saturated, not pastel) — QB and
// K were previously swapped hues (QB pale violet, K pale pink) against
// Sleeper's rose-red QB / violet K, and RB/WR were noticeably more washed
// out than Sleeper's bolder fills.
export const positionColors: Record<string, string> = {
  QB: '#FB7185',
  RB: '#4ADE80',
  WR: '#38BDF8',
  TE: '#FB923C',
  K: '#A78BFA',
  DEF: '#D4D4D8',
  DST: '#D4D4D8',
};

export function positionColor(position: string | null | undefined): string {
  return positionColors[(position ?? '').toUpperCase()] ?? colors.textSecondary;
}

export const gradients = {
  hero: ['#16202C', '#0D1117'] as const,
  accent: ['#5CE4FF', '#00D4FF'] as const,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

/**
 * Named after the brand sheet's structure rather than a size scale:
 * `md`/`pill` are the two values almost everything uses (card corners and
 * fully-round chips/avatars/buttons). `sm`/`lg` cover the smaller and
 * larger ends (tiny inline tags; bottom sheets and modals).
 */
// Ported verbatim from the web app's canonical geometry scale
// (modules/design_tokens.py: --radius-sm/md/lg/control/panel are all 0 —
// "a small intentional scale (square / control / panel / pill / segment)").
// Hard edges are a deliberate brand choice there, not an oversight — only
// genuine segmented filter chips get a true pill (--radius-segment: 999px).
// Apple-style elevation/motion (see `shadows`/`motion` below) comes from
// shadow depth and spring animation, not rounded corners.
export const radii = {
  sm: 0,
  md: 0,
  lg: 0,
  pill: 999,
  tile: 0,
  input: 0,
};

export const typography = {
  display: { fontSize: 34, fontWeight: '700' as const, letterSpacing: -0.5 },
  title: { fontSize: 22, fontWeight: '700' as const },
  heading: { fontSize: 17, fontWeight: '600' as const },
  body: { fontSize: 15, fontWeight: '400' as const },
  bodyMuted: { fontSize: 13, fontWeight: '400' as const },
  label: { fontSize: 12, fontWeight: '600' as const },
  kicker: { fontSize: 11, fontWeight: '600' as const, letterSpacing: 0.8 },
  caption: { fontSize: 11, fontWeight: '500' as const },
  badge: { fontSize: 9, fontWeight: '800' as const, letterSpacing: 0.3 },
};

/**
 * Apple-style dark-mode elevation: a black drop shadow alone reads as a
 * smudge on a near-black background, so every level pairs a shadow with a
 * hairline "rim" border (applied separately via `colors.border`/
 * `colors.borderStrong`) — components add the border, these just provide
 * the shadow/elevation half.
 */
export const shadows = {
  resting: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 12, shadowOffset: { width: 0, height: 6 } },
    android: { elevation: 6 },
    default: {},
  }),
  pressed: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.28, shadowRadius: 6, shadowOffset: { width: 0, height: 2 } },
    android: { elevation: 2 },
    default: {},
  }),
  sheet: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.6, shadowRadius: 28, shadowOffset: { width: 0, height: -8 } },
    android: { elevation: 16 },
    default: {},
  }),
  modal: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.6, shadowRadius: 28, shadowOffset: { width: 0, height: 12 } },
    android: { elevation: 16 },
    default: {},
  }),
  orb: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.55, shadowRadius: 18, shadowOffset: { width: 0, height: 10 } },
    android: { elevation: 14 },
    default: {},
  }),
  orbGlow: Platform.select({
    ios: { shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 14, shadowOffset: { width: 0, height: 0 } },
    android: {},
    default: {},
  }),
  focus: Platform.select({
    ios: { shadowColor: colors.accent, shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 0 } },
    android: { elevation: 4 },
    default: {},
  }),
};

/** Legacy alias — prefer `shadows.resting` in new code. */
export const cardShadow = shadows.resting;

/** Named springs/easings for reanimated — see AnimatedCard/GmOrb for usage. */
export const motion = {
  pressSpring: { damping: 18, stiffness: 320, mass: 0.7 },
  sheetSpring: { damping: 28, stiffness: 260, mass: 1, overshootClamping: true },
  easeOutQuintMs: 320,
};

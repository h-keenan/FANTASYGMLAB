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

/**
 * Dark surface ramp — three steppable solid tiers (background < surface <
 * backgroundElevated) plus two line weights (border < borderStrong).
 * `background` is true OLED black per direct feedback (2026-09-22) — every
 * other tier shifted down the same ramp so the *relative* contrast steps
 * that made the original ramp legible are preserved, just anchored to #000
 * instead of #0D1117.
 *
 * Relative contrast between neighbours:
 *   surface -> backgroundElevated  ~1.26
 *   backgroundElevated -> border   ~1.19
 *   border -> borderStrong         ~1.28
 * `border` deliberately sits *above* `backgroundElevated` so a rim reads on
 * all three surfaces — in dark mode a rim catches light, it doesn't cut a
 * groove. Hue stays 213-217deg throughout, desaturating slightly as it
 * lightens so the top of the ramp doesn't skew blue.
 *
 * `border` is a *line* token: for solid chip/track/disc fills use
 * `backgroundElevated`, never `border`.
 */
const darkColors = {
  background: '#000000',
  backgroundElevated: '#1A1F26',
  surface: '#0D1117',
  surfaceSolid: '#0D1117',
  border: '#242E3B',
  borderStrong: '#2E3A4A',
  // Concept-sheet card outline: every card there reads with a faint cyan
  // edge against the navy background, not a neutral gray hairline. Scoped
  // to AnimatedCard's default border only (never swapped in for the
  // generic `border`/`borderStrong` line tokens, which stay neutral for
  // dividers, inputs, and non-card outlines) so this doesn't cascade into
  // unrelated UI that was never meant to look "branded."
  cardBorder: 'rgba(92,228,255,0.28)',
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
 * Light theme: "glacier ice white" per direct feedback (2026-09-22) — a
 * cool pale-blue backdrop (not stark white) with pure-white cards standing
 * up off it, and the same brand hues darkened just enough to clear AA text
 * contrast on a light ground (the dark theme's accent/danger/success/
 * premium are tuned for a near-black backdrop and fail contrast used as
 * text here).
 */
const lightColors = {
  background: '#EAF3F8',
  backgroundElevated: '#D9E8F0',
  surface: '#FFFFFF',
  surfaceSolid: '#FFFFFF',
  border: '#C7D9E3',
  borderStrong: '#AFC7D5',
  cardBorder: 'rgba(0,120,160,0.25)',
  hairline: 'rgba(10,30,45,0.08)',
  textPrimary: '#0B1D26',
  textSecondary: '#3E5867',
  textTertiary: '#6B8494',
  accent: '#0077A3',
  accentSoft: '#00A6CC',
  accentMuted: 'rgba(0,119,163,0.12)',
  danger: '#D92D2D',
  dangerMuted: 'rgba(217,45,45,0.12)',
  success: '#178A43',
  successBright: '#22C55E',
  successMuted: 'rgba(23,138,67,0.12)',
  premium: '#B8860B',
  premiumMuted: 'rgba(184,134,11,0.12)',
  badgeBackground: 'rgba(0,119,163,0.12)',
  badgeText: '#0077A3',
  violet: '#6B5FCC',
};

export type ThemeColors = typeof darkColors;
export { darkColors, lightColors };

/**
 * Default/legacy export — every screen that hasn't migrated to
 * `useThemeMode()` yet (see context/ThemeModeContext.tsx) still imports
 * this directly and always renders in dark, exactly as before. Screens
 * migrated to the new theme system read `colors` from the hook instead of
 * this static export so they actually respond to the Day/Night/Auto
 * toggle — see ThemeModeContext's own docstring for the migration status
 * and why a static export couldn't just be reassigned in place (React
 * Native bakes StyleSheet.create's values in at module-load time, so
 * mutating this object's properties would not update any already-created
 * style sheet).
 */
export const colors = darkColors;

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

// coridian_ (2026-09-22): "a lot of the colored aspects blend in" on light
// mode. `positionColors` above was never given a light-mode counterpart —
// those pastel dark-mode fills pop against near-black but read as barely-
// there washes against glacier-white/pale-blue surfaces. These are the same
// hues pushed several steps darker/more saturated so PositionBadge's chip
// text stays legible on light backgrounds too.
export const positionColorsLight: Record<string, string> = {
  QB: '#BE123C',
  RB: '#15803D',
  WR: '#0369A1',
  TE: '#C2410C',
  K: '#6D28D9',
  DEF: '#3F3F46',
  DST: '#3F3F46',
};

export function positionColor(
  position: string | null | undefined,
  isDark = true,
  fallback: string = colors.textSecondary,
): string {
  const table = isDark ? positionColors : positionColorsLight;
  return table[(position ?? '').toUpperCase()] ?? fallback;
}

export const gradients = {
  hero: ['#16202C', '#000000'] as const,
  accent: ['#5CE4FF', '#00D4FF'] as const,
};

export const lightGradients = {
  hero: ['#FFFFFF', '#EAF3F8'] as const,
  accent: ['#00A6CC', '#0077A3'] as const,
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

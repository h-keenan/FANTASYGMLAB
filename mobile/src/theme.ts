import { Platform } from 'react-native';

/**
 * Shared design tokens — colors, spacing, radii, and a native-feeling card
 * shadow. Kept deliberately small: this is a client-side presentation layer
 * only, it doesn't encode any product/valuation logic.
 *
 * These are the actual FantasyGM Lab brand values (modules/brand_identity.py
 * on the web app — BRAND_BG/BRAND_ACCENT/etc.), not an independently invented
 * dark palette, so the mobile app reads as the same product as the web app.
 */

export const colors = {
  background: '#050607', // BRAND_BG
  backgroundElevated: '#1B1E23', // BRAND_SURFACE_RAISED
  surface: 'rgba(255,255,255,0.05)',
  surfaceSolid: '#0F1114', // BRAND_SURFACE
  border: 'rgba(255,255,255,0.10)',
  borderStrong: 'rgba(255,255,255,0.18)',
  textPrimary: '#F8FAFC', // BRAND_TEXT
  textSecondary: '#A8ADB7', // BRAND_TEXT_MUTED
  textTertiary: '#6B7280',
  accent: '#22D3EE', // BRAND_ACCENT (Analyze trajectory cyan)
  accentSoft: '#67E8F9', // BRAND_ACCENT_SOFT
  accentMuted: 'rgba(34,211,238,0.16)',
  danger: '#EF4444', // BRAND_TRAJECTORY_EXECUTE
  dangerMuted: 'rgba(239,68,68,0.16)',
  success: '#22C55E', // BRAND_SUCCESS
  successMuted: 'rgba(34,197,94,0.16)',
  premium: '#FACC15', // BRAND_PREMIUM / BRAND_TRAJECTORY_PROJECT
  premiumMuted: 'rgba(250,204,21,0.16)',
  badgeBackground: 'rgba(34,211,238,0.18)',
  badgeText: '#67E8F9',
};

export const gradients = {
  hero: ['#1B2340', '#050607'] as const,
  accent: ['#67E8F9', '#22D3EE'] as const,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

/**
 * The web app's actual FGL identity (modules/design_tokens.py) is a sharp,
 * bordered "dossier" look — --radius-* is 0 everywhere, even "pills" are a
 * near-square 2px. Mobile keeps a small amount of rounding for touch
 * affordance (fully square controls read as broken on iOS/Android), but
 * stays much closer to that flat, editorial identity than generic rounded
 * mobile-card defaults would.
 */
export const radii = {
  sm: 6,
  md: 8,
  lg: 12,
  pill: 6,
};

export const typography = {
  title: { fontSize: 22, fontWeight: '700' as const },
  heading: { fontSize: 17, fontWeight: '700' as const },
  body: { fontSize: 14, fontWeight: '400' as const },
  label: { fontSize: 12, fontWeight: '600' as const },
  caption: { fontSize: 11, fontWeight: '500' as const },
};

/**
 * A soft elevation for card surfaces. Dark surfaces barely show a shadow, so
 * this stays subtle and does most of its work through `colors.border`
 * instead — the glass-card look leans on translucency + hairline borders,
 * not drop shadow, to read as "elevated" against a near-black background.
 */
export const cardShadow = Platform.select({
  ios: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
  },
  android: {
    elevation: 4,
  },
  default: {},
});

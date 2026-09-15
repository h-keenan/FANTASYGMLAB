import { Platform } from 'react-native';

/**
 * Shared design tokens — colors, spacing, radii, and a native-feeling card
 * shadow. Kept deliberately small: this is a client-side presentation layer
 * only, it doesn't encode any product/valuation logic.
 *
 * Dark-first palette: fantasy sports apps (Sleeper, ESPN Fantasy) live in
 * dark mode by default, and it reads as "trading desk," not "spreadsheet."
 */

export const colors = {
  background: '#0B0E14',
  backgroundElevated: '#11151F',
  surface: 'rgba(255,255,255,0.05)',
  surfaceSolid: '#161B26',
  border: 'rgba(255,255,255,0.10)',
  borderStrong: 'rgba(255,255,255,0.18)',
  textPrimary: '#F3F5F9',
  textSecondary: '#8A93A6',
  textTertiary: '#5B6478',
  accent: '#5B8DEF',
  accentMuted: 'rgba(91,141,239,0.16)',
  danger: '#F0596A',
  dangerMuted: 'rgba(240,89,106,0.16)',
  success: '#2ECC8F',
  successMuted: 'rgba(46,204,143,0.16)',
  badgeBackground: 'rgba(91,141,239,0.18)',
  badgeText: '#9DBBFA',
};

export const gradients = {
  hero: ['#1B2340', '#0B0E14'] as const,
  accent: ['#6E9BFF', '#5B8DEF'] as const,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

export const radii = {
  sm: 10,
  md: 14,
  lg: 20,
  pill: 999,
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

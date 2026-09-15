import { Platform } from 'react-native';

/**
 * Shared design tokens — colors, spacing, radii, and a native-feeling card
 * shadow. Kept deliberately small: this is a client-side presentation layer
 * only, it doesn't encode any product/valuation logic.
 */

export const colors = {
  background: '#F2F2F7', // iOS system grouped background
  surface: '#FFFFFF',
  border: '#E5E5EA',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  accent: '#2563EB',
  danger: '#DC2626',
  success: '#16A34A',
  badgeBackground: '#111827',
  badgeText: '#FFFFFF',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

export const radii = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
};

/**
 * A soft, native-feeling elevation for card surfaces — iOS uses shadow
 * props, Android uses `elevation` (which also implies its own shadow), so
 * both are set and each platform picks what it understands.
 */
export const cardShadow = Platform.select({
  ios: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
  },
  android: {
    elevation: 3,
  },
  default: {},
});

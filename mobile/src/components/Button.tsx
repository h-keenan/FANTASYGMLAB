import React, { useMemo } from 'react';
import { ActivityIndicator, StyleProp, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';

import AppText from './AppText';
import PremiumGlow from './PremiumGlow';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, type ThemeColors } from '../theme';

/**
 * The one button. `primary` is `onAccent` ink on the accent fill (dark ink on
 * dark-theme cyan; never a hard-coded white), `secondary` is outlined,
 * `ghost` is a text action, `premium` is dark ink on the gold fill with a soft
 * pulsing gold glow (EVERY premium-related control), `premiumOutline` its
 * gold-outline sibling (Restore purchases), `danger` / `dangerOutline` are the destructive
 * fill and outline, `loading` swaps the label for a spinner. Mirrors web-next's components/Button.tsx.
 */
export default function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
  size = 'md',
  style,
}: {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'dangerOutline' | 'premium' | 'premiumOutline';
  disabled?: boolean;
  loading?: boolean;
  /** `sm` mirrors web's size="sm" (compact padding, 12px label). */
  size?: 'sm' | 'md';
  style?: StyleProp<ViewStyle>;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors, isDark), [colors, isDark]);
  // Web parity: a disabled (not loading) button swaps to the muted surface
  // fill + muted ink (filled variants) or muted ink + strong border
  // (outline/ghost) instead of fading; loading keeps the opacity fade.
  const showDisabled = disabled && !loading;
  const liveInk =
    variant === 'primary' || variant === 'danger'
      ? colors.onAccent
      : variant === 'premium'
        ? colors.onPremium
        : variant === 'premiumOutline'
          ? colors.premium
          : variant === 'secondary'
        ? colors.textPrimary
        : variant === 'dangerOutline'
          ? colors.danger
          : colors.accent;
  const inkColor = showDisabled ? colors.textTertiary : liveInk;
  const button = (
    <TouchableOpacity
      accessibilityRole="button"
      style={[
        styles.base,
        size === 'sm' && styles.baseSm,
        styles[variant],
        showDisabled && styles[`${variant}Disabled` as const],
        loading && styles.disabled,
        variant !== 'premium' && style]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator color={inkColor} />
      ) : (
        <AppText style={[styles.text, size === 'sm' && styles.textSm, { color: inkColor }]}>{label}</AppText>
      )}
    </TouchableOpacity>
  );
  if (variant !== 'premium') return button;
  // The glow wraps the button; layout props (alignSelf/margin/flex) go on the wrapper so it sizes the same.
  return (
    <PremiumGlow radius={radii.md} active={!(disabled || loading)} style={style}>
      {button}
    </PremiumGlow>
  );
}

function createStyles(colors: ThemeColors, isDark: boolean) {
  // Web --color-surface-muted: pure black in dark, the pale chip fill in light.
  const mutedFill = isDark ? colors.background : colors.backgroundElevated;
  return StyleSheet.create({
    base: {
      minHeight: 44,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      alignItems: 'center',
      justifyContent: 'center',
    },
    baseSm: { minHeight: 36, paddingVertical: spacing.sm, paddingHorizontal: spacing.md },
    primary: { backgroundColor: colors.accentStrong },
    secondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.borderStrong },
    ghost: { backgroundColor: 'transparent' },
    premium: { backgroundColor: colors.premiumFill },
    premiumOutline: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.premium },
    danger: { backgroundColor: colors.danger },
    dangerOutline: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.danger },
    primaryDisabled: { backgroundColor: mutedFill },
    premiumDisabled: { backgroundColor: mutedFill },
    dangerDisabled: { backgroundColor: mutedFill },
    secondaryDisabled: {},
    ghostDisabled: {},
    premiumOutlineDisabled: { borderColor: colors.borderStrong },
    dangerOutlineDisabled: { borderColor: colors.borderStrong },
    disabled: { opacity: disabledOpacity },
    text: { fontSize: 15, fontWeight: '700' },
    textSm: { fontSize: 13 },
  });
}

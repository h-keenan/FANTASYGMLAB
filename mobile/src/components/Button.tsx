import React, { useMemo } from 'react';
import { ActivityIndicator, StyleProp, StyleSheet, TouchableOpacity, ViewStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, type ThemeColors } from '../theme';

/**
 * The one button. `primary` is `onAccent` ink on the accent fill (dark ink on
 * dark-theme cyan; never a hard-coded white), `secondary` is outlined,
 * `ghost` is a text action, `danger` / `dangerOutline` are the destructive
 * fill and outline, `loading` swaps the label for a spinner. Mirrors web-next's components/Button.tsx.
 */
export default function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
  style,
}: {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'dangerOutline';
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const inkColor =
    variant === 'primary' || variant === 'danger'
      ? colors.onAccent
      : variant === 'secondary'
        ? colors.textPrimary
        : variant === 'dangerOutline'
          ? colors.danger
          : colors.accent;
  return (
    <TouchableOpacity
      accessibilityRole="button"
      style={[styles.base, styles[variant], (disabled || loading) && styles.disabled, style]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator color={inkColor} />
      ) : (
        <AppText style={[styles.text, { color: inkColor }]}>{label}</AppText>
      )}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    base: {
      minHeight: 44,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      alignItems: 'center',
      justifyContent: 'center',
    },
    primary: { backgroundColor: colors.accent },
    secondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.borderStrong },
    ghost: { backgroundColor: 'transparent' },
    danger: { backgroundColor: colors.danger },
    dangerOutline: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.danger },
    disabled: { opacity: disabledOpacity },
    text: { fontSize: 15, fontWeight: '700' },
  });
}

import React, { useMemo } from 'react';
import { StyleSheet, TextInput, type StyleProp, type TextInputProps, type TextStyle } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The one text input: web `.glass-input` fill + rim, `radii.input` (web control radius), 44pt minimum
 * height and the theme placeholder color. `invalid` swaps the border to the
 * danger lane. Mirrors web-next's components/Input.tsx.
 */
export default function Input({
  invalid = false,
  style,
  ...rest
}: TextInputProps & { invalid?: boolean; style?: StyleProp<TextStyle> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TextInput
      placeholderTextColor={colors.textTertiary}
      {...rest}
      style={[styles.input, invalid && styles.invalid, style]}
    />
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    input: {
      minHeight: 44,
      borderWidth: 1,
      borderColor: colors.glassInputBorder,
      borderRadius: radii.input,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      fontSize: 16,
      backgroundColor: colors.glassInput,
      color: colors.textPrimary,
    },
    invalid: { borderColor: colors.danger },
  });
}

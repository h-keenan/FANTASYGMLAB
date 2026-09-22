import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';

import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The concept sheet's empty-state panel (icon + headline + subtext, an
 * optional CTA) — every list screen in the app used to fall back to a
 * single plain gray line instead. One shared component so every empty
 * list reads as "considered," not "we forgot to build this state."
 */
export default function EmptyState({
  icon,
  title,
  subtitle,
  actionLabel,
  onPressAction,
}: {
  icon: IconName;
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onPressAction?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.container}>
      <IconCircle name={icon} color={colors.accent} size={56} iconSize={26} />
      <AppText style={styles.title}>{title}</AppText>
      {subtitle ? <AppText style={styles.subtitle}>{subtitle}</AppText> : null}
      {actionLabel && onPressAction ? (
        <TouchableOpacity style={styles.button} onPress={onPressAction}>
          <AppText style={styles.buttonText}>{actionLabel}</AppText>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.xxl,
      paddingHorizontal: spacing.xl,
      gap: spacing.xs,
    },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginTop: spacing.sm },
    subtitle: { fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 },
    button: {
      marginTop: spacing.md,
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.sm,
      borderRadius: radii.pill,
      backgroundColor: colors.accent,
    },
    buttonText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  });
}

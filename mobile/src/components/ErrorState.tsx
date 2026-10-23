import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The one "couldn't load" state: danger icon, headline, the human-readable
 * reason, and a Retry button. Mirrors web-next's ErrorState. Screens used to
 * borrow `EmptyState` (no semantic error treatment) or print a bare red
 * line; `EmptyState` stays for true empty lists.
 */
export default function ErrorState({
  title = "Couldn't load this",
  message,
  onRetry,
  retryLabel = 'Try again',
  icon = 'alert-circle-outline',
  compact = false,
}: {
  title?: string;
  message?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
  icon?: IconName;
  /** Inline variant for an error above content that is still on screen. */
  compact?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.container, compact && styles.compact]} accessibilityRole="alert">
      <IconCircle name={icon} color={colors.danger} size={compact ? 40 : 56} iconSize={compact ? 20 : 26} />
      <AppText style={styles.title}>{title}</AppText>
      {message ? <AppText style={styles.message}>{message}</AppText> : null}
      {onRetry ? <Button label={retryLabel} onPress={onRetry} style={styles.button} /> : null}
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
    compact: { paddingVertical: spacing.lg },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginTop: spacing.sm },
    message: { fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 },
    button: { marginTop: spacing.md, paddingVertical: spacing.sm },
  });
}

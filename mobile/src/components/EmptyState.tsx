import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';

import Button from './Button';
import GlassCard from './GlassCard';
import IconCircle from './IconCircle';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The one empty state, matching web-next's EmptyState (2026-10-27 parity):
 * a glass card with an accent left rail, an icon disc, a bold title, a muted
 * one-line reason and, when there is a next step, a small button.
 */
export default function EmptyState({
  icon,
  title,
  subtitle,
  actionLabel,
  onPressAction,
  actionVariant,
  secondaryLabel,
  onPressSecondary,
}: {
  icon: IconName;
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onPressAction?: () => void;
  /** Use 'premium' when the CTA is an upgrade (gold, glowing). */
  actionVariant?: 'primary' | 'premium';
  /** Optional lightweight text link under the primary action — for a
   * secondary path (e.g. "Don't have a league yet?") that shouldn't compete
   * visually with the main CTA button above it. */
  secondaryLabel?: string;
  onPressSecondary?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <GlassCard style={styles.container}>
      <IconCircle name={icon} color={colors.accent} size={44} iconSize={22} />
      <View style={styles.body}>
        <AppText style={styles.title}>{title}</AppText>
        {subtitle ? <AppText style={styles.subtitle}>{subtitle}</AppText> : null}
        {actionLabel && onPressAction ? (
          <Button label={actionLabel} onPress={onPressAction} variant={actionVariant} size="sm" style={styles.button} />
        ) : null}
        {secondaryLabel && onPressSecondary ? (
          <TouchableOpacity onPress={onPressSecondary} hitSlop={8} style={styles.secondaryLink}>
            <AppText style={styles.secondaryLinkText}>{secondaryLabel}</AppText>
          </TouchableOpacity>
        ) : null}
      </View>
    </GlassCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    // Web: px-4 py-6, gap-1, items-start. Stretch so centered screen wrappers
    // still give a full-width card.
    container: {
      alignSelf: 'stretch',
      flexDirection: 'row',
      alignItems: 'flex-start',
      paddingVertical: spacing.lg,
      paddingHorizontal: spacing.lg,
      gap: spacing.md,
      borderLeftWidth: 3,
      borderLeftColor: colors.accent,
    },
    body: { flex: 1, minWidth: 0, alignItems: 'flex-start', gap: spacing.xs },
    title: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    subtitle: { fontSize: 13.5, color: colors.textTertiary, lineHeight: 19 },
    button: { marginTop: spacing.sm, alignSelf: 'flex-start' },
    secondaryLink: { marginTop: spacing.sm, padding: spacing.xs },
    secondaryLinkText: {
      fontSize: 13.5,
      fontWeight: '600',
      color: colors.textTertiary,
      textDecorationLine: 'underline',
    },
  });
}

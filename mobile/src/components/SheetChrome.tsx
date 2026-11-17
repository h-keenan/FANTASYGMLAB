import React, { useMemo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * THE sheet / popup chrome (header rewrite phase 4; docs/audits/2026-11-header-rewrite.md, "Sheet" template). Twin of web-next's
 * components/ui/SheetChrome.tsx: one round glass close button and one title row (leading, title, subtitle, actions, close), so `Sheet`,
 * the player quick view, the Sim sheet, the trade picker, the percentile explorer and the manager profile no longer each draw their own.
 */
export function SheetCloseButton({ label, onClose, testID }: { label: string; onClose: () => void; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <Pressable onPress={onClose} hitSlop={10} style={styles.close} accessibilityRole="button" accessibilityLabel={label} testID={testID}>
      <Ionicons name="close" size={18} color={colors.textSecondary} />
    </Pressable>
  );
}

export type SheetHeaderProps = {
  title: string;
  subtitle?: string | null;
  /** Keep the title for assistive tech but hide it visually. */
  hideTitle?: boolean;
  leading?: ReactNode;
  /** Controls between the title and the close button. */
  actions?: ReactNode;
  onClose: () => void;
  closeLabel?: string;
};

/** Title, subtitle, actions and the close button on one row. */
export function SheetHeader({ title, subtitle, hideTitle = false, leading, actions, onClose, closeLabel }: SheetHeaderProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.row}>
      {leading}
      <View style={styles.text}>
        <AppText accessibilityRole="header" style={hideTitle ? styles.srOnly : styles.title} numberOfLines={2}>
          {title}
        </AppText>
        {subtitle ? <AppText style={styles.subtitle}>{subtitle}</AppText> : null}
      </View>
      {actions}
      <SheetCloseButton label={closeLabel ?? `Close ${title}`} onClose={onClose} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    text: { flex: 1, minWidth: 0 },
    title: { fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    subtitle: { fontSize: 13, color: colors.textTertiary, marginTop: 2 },
    srOnly: { position: 'absolute', width: 1, height: 1, opacity: 0 },
    close: {
      width: 32,
      height: 32,
      borderRadius: radii.pill,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
    },
  });
}

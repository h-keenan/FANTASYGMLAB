import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { withAlpha } from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing } from '../theme';

export type IconRowIcon = 'check' | 'alert' | 'info' | 'arrow' | 'clock' | 'flag';

const GLYPH: Record<IconRowIcon, keyof typeof Ionicons.glyphMap> = {
  check: 'checkmark',
  alert: 'alert',
  info: 'information',
  arrow: 'arrow-forward',
  clock: 'time-outline',
  flag: 'flag',
};

/**
 * A small tinted icon in a soft round chip followed by text: the replacement
 * for literal bullet characters. Mirrors web-next's IconRow (PR #1696).
 * `color` is a semantic theme color, never a raw hex.
 */
export default function IconRow({
  icon = 'arrow',
  color,
  children,
  textStyle,
}: {
  icon?: IconRowIcon;
  color?: string;
  children: React.ReactNode;
  textStyle?: object;
}) {
  const { colors } = useThemeMode();
  const tint = color ?? colors.textTertiary;
  return (
    <View style={styles.row}>
      <View style={[styles.chip, { backgroundColor: withAlpha(tint, 0.16) }]}>
        <Ionicons name={GLYPH[icon]} size={12} color={tint} />
      </View>
      <AppText style={[styles.text, { color: colors.textSecondary }, textStyle]}>{children}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  chip: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  text: { flex: 1, minWidth: 0, fontSize: 13, lineHeight: 18, paddingTop: 1 },
});

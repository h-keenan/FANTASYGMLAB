import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The one section title: UPPERCASE with tight tracking (owner decision 1).
 * Optional accent icon, a muted `caption` line under it, and a `right` slot
 * (a total, a link). Replaces the seven screen-local uppercase kicker
 * restyles (DraftCenter, TeamRoster, MyTeam, TradeFinder, More, Waivers) and
 * the old Title Case icon heading. `topGap` is the space above it inside a
 * scroll column.
 */
export default function SectionHeading({
  title,
  icon,
  caption,
  right,
  topGap = 0,
}: {
  title: string;
  icon?: IconName;
  caption?: string | null;
  right?: React.ReactNode;
  topGap?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.wrap, { marginTop: topGap }]}>
      <View style={styles.row}>
        {icon ? <Ionicons name={icon} size={14} color={colors.accent} style={styles.icon} /> : null}
        <AppText style={styles.title} numberOfLines={1} accessibilityRole="header">
          {title}
        </AppText>
        {right ? <View style={styles.right}>{right}</View> : null}
      </View>
      {caption ? <AppText style={styles.caption}>{caption}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { marginBottom: spacing.sm, gap: 2 },
    row: { flexDirection: 'row', alignItems: 'center' },
    icon: { marginRight: spacing.xs },
    title: {
      flexShrink: 1,
      fontSize: 12,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    right: { marginLeft: 'auto' },
    caption: { fontSize: 11.5, color: colors.textTertiary },
  });
}

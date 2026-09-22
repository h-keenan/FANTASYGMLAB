import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * The concept sheet's dramatic per-screen hero statement (big bold italic
 * screen name + league name beneath it) — first built inline on Dashboard
 * only, which is exactly why every other screen still read as "unchanged"
 * even after Dashboard itself matched. One shared component so it's
 * actually applied everywhere the concept sheets show it, not just one
 * screen. Sits inside the scrollable content, below the compact shared nav
 * title every screen already has (ScreenHeaderTitle) — this is additional
 * content, not a replacement for that shared nav header.
 */
export default function ScreenHero({ title, subtitle }: { title: string; subtitle: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.heroBlock}>
      <AppText style={styles.heroTitle}>{title}</AppText>
      {subtitle ? (
        <AppText style={styles.heroSubtitle} numberOfLines={1}>
          {subtitle.toUpperCase()}
        </AppText>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    heroBlock: { alignItems: 'center', marginBottom: spacing.md },
    heroTitle: {
      fontSize: 30,
      fontWeight: '800',
      fontStyle: 'italic',
      color: colors.textPrimary,
      letterSpacing: 0.5,
    },
    heroSubtitle: {
      fontSize: 12,
      fontWeight: '700',
      color: colors.textSecondary,
      letterSpacing: 1.4,
      marginTop: 2,
    },
  });
}

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

/**
 * Two-line centered header title: screen name on top, league name (small,
 * muted, uppercase) beneath. Replaces the old "Screen — League Name" single
 * string, which repeated the league name at full size on every screen and
 * combined with the native back-button pill to read as duplicated chrome.
 */
export default function ScreenHeaderTitle({ screen, league }: { screen: string; league?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.container}>
      <AppText style={styles.screen} numberOfLines={1}>
        {screen}
      </AppText>
      {league ? (
        <AppText style={styles.league} numberOfLines={1}>
          {league.toUpperCase()}
        </AppText>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { alignItems: 'center', maxWidth: 220 },
    screen: { fontSize: 17, fontWeight: '600', color: colors.textPrimary },
    league: {
      fontSize: 11,
      fontWeight: '600',
      color: colors.textSecondary,
      letterSpacing: 0.8,
      marginTop: 1,
    },
  });
}

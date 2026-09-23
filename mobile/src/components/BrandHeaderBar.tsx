import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AppText from './AppText';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * The concept sheet's persistent branded bar (wordmark + star + more-menu)
 * that sits at the top of every screen's scrollable content — additive
 * content, not a replacement for the native stack header's back button, so
 * it carries no back control of its own. The native header (ScreenHeaderTitle)
 * is the single source of truth for the screen title and league name; this
 * used to sit below a second, redundant repeat of both (ScreenHero, removed
 * per coridian_: "the top of many of the pages looks bad and pasted text").
 *
 * Star and "…" are real navigation shortcuts (GM Targets, More), not
 * decorative — this app's rule is no button that does nothing.
 */
export default function BrandHeaderBar({
  leagueId,
  leagueName,
}: {
  leagueId?: string;
  leagueName?: string;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  return (
    <View style={styles.row}>
      <View style={styles.side} />
      <View style={styles.centerGroup}>
        <View style={styles.accentLine} />
        <AppText style={styles.wordmark}>
          FANTASY<AppText style={styles.wordmarkAccent}>GM</AppText>LAB
        </AppText>
        <View style={styles.accentLine} />
      </View>
      <View style={[styles.side, styles.actions]}>
        {leagueId && leagueName ? (
          <TouchableOpacity
            style={styles.iconButton}
            hitSlop={8}
            onPress={() => navigation.navigate('GmTargets', { leagueId, leagueName })}
          >
            <Ionicons name="star-outline" size={17} color={colors.accent} />
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity style={styles.iconButton} hitSlop={8} onPress={() => navigation.navigate('More')}>
          <Ionicons name="ellipsis-horizontal" size={17} color={colors.textPrimary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  side: { flex: 1 },
  centerGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  accentLine: {
    width: 16,
    height: StyleSheet.hairlineWidth * 3,
    backgroundColor: colors.border,
  },
  wordmark: {
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 1,
    color: colors.textPrimary,
  },
  wordmarkAccent: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.accent,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
  },
  iconButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  });
}

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';

import AppText from './AppText';
import PlatformBadge from './PlatformBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { CONNECT_PLATFORMS, type ConnectPlatformKey } from '../lib/connectFlow';
import { radii, spacing, type ThemeColors } from '../theme';

export type LeaguePlatformKey = ConnectPlatformKey;

/**
 * The five equal platform tiles of Add a league (Sleeper, Yahoo, ESPN, Fleaflicker, MFL), each a brand-color monogram badge,
 * the name and a one-word hint. Tapping a tile hands the platform to the screen, which then shows only that platform's step.
 * Mirrors web-next's tile grid in SleeperImportForm.
 */
export default function PlatformPicker({ onChange }: { onChange: (platform: LeaguePlatformKey) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.grid}>
      {CONNECT_PLATFORMS.map((option) => (
        <PressableScale
          key={option.key}
          style={styles.tile}
          onPress={() => onChange(option.key)}
          accessibilityRole="button"
          accessibilityLabel={`${option.label}, ${option.hint}`}
          testID={`platform-tile-${option.key}`}
        >
          <PlatformBadge platform={option.key} size={44} />
          <AppText style={styles.title}>{option.label}</AppText>
          <AppText style={styles.hint}>{option.hint}</AppText>
        </PressableScale>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    // Equal tiles, three per row (the last row holds two; no stretching).
    tile: {
      width: '31.5%',
      alignItems: 'center',
      gap: 4,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    title: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    hint: { fontSize: 13, color: colors.textTertiary },
  });
}

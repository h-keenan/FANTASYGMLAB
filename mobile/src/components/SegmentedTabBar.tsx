import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface SegmentedTabOption<T extends string> {
  key: T;
  label: string;
}

/**
 * One cohesive segmented control — a single shared track holding all
 * options, with the active option rendered as an illuminated cyan pill and
 * every other option as plain understated text — replacing the old row of
 * individually-bordered pill buttons (which read as a set of disconnected
 * buttons rather than one control). Generic over the tab key type so it can
 * back Player Detail's Stats/Trends/Schedule/Career/Model tabs today and any
 * other screen's tab row later without a second implementation.
 */
export default function SegmentedTabBar<T extends string>({
  options,
  active,
  onChange,
}: {
  options: Array<SegmentedTabOption<T>>;
  active: T;
  onChange: (key: T) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.track}>
      {options.map((option) => {
        const isActive = option.key === active;
        return (
          <TouchableOpacity
            key={option.key}
            style={[styles.segment, isActive && styles.segmentActive]}
            onPress={() => onChange(option.key)}
            activeOpacity={0.75}
          >
            <AppText style={[styles.label, isActive && styles.labelActive]} numberOfLines={1}>
              {option.label}
            </AppText>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    track: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.background,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      padding: 3,
      gap: 2,
    },
    segment: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.sm - 2,
      borderRadius: radii.pill,
    },
    segmentActive: {
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    label: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    // accentOnTint, not accent: this label sits directly on `segmentActive`'s
    // accentMuted fill, where light mode's plain accent falls under AA
    // contrast (color-system audit, 2026-09-25 — see theme.ts).
    labelActive: { color: colors.accentOnTint, fontWeight: '700' },
  });
}

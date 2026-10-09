import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { PlayerListViewMode } from '../lib/viewModePreference';

/**
 * Compact icon-pair toggle between the full-width List view and the 2-up
 * compact Grid view on dense player-list screens (Players, Waivers, College
 * Prospects). Same track/active-pill visual language as SegmentedTabBar
 * (illuminated cyan pill for the active option, quiet otherwise) but icon-
 * only rather than text-label, since "List"/"Grid" need no caption to read
 * at a glance and a text version would crowd the filter row these screens
 * already have.
 */
export default function ViewModeToggle({
  value,
  onChange,
}: {
  value: PlayerListViewMode;
  onChange: (mode: PlayerListViewMode) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.track} accessibilityRole="tablist">
      <TouchableOpacity
        style={[styles.segment, value === 'list' && styles.segmentActive]}
        onPress={() => onChange('list')}
        activeOpacity={0.75}
        accessibilityRole="tab"
        accessibilityState={{ selected: value === 'list' }}
        accessibilityLabel="List view"
        hitSlop={6}
      >
        <Ionicons
          name="reorder-three-outline"
          size={16}
          color={value === 'list' ? colors.accentOnTint : colors.textSecondary}
        />
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.segment, value === 'grid' && styles.segmentActive]}
        onPress={() => onChange('grid')}
        activeOpacity={0.75}
        accessibilityRole="tab"
        accessibilityState={{ selected: value === 'grid' }}
        accessibilityLabel="Grid view"
        hitSlop={6}
      >
        <Ionicons
          name="grid-outline"
          size={15}
          color={value === 'grid' ? colors.accentOnTint : colors.textSecondary}
        />
      </TouchableOpacity>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    track: {
      flexDirection: 'row',
      alignItems: 'center',
      alignSelf: 'flex-start',
      backgroundColor: colors.background,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      padding: 3,
      gap: 2,
    },
    segment: {
      width: 30,
      height: 26,
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: radii.pill,
    },
    segmentActive: {
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
  });
}

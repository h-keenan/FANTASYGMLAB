import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface SegmentedTabOption<T extends string> {
  key: T;
  label: string;
  /** Optional glyph slot, stacked over the label on phones (tab icons are added in this one place). */
  icon?: React.ReactNode;
  /** Small count pill beside the label. */
  count?: number;
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
  scrollable = false,
}: {
  options: Array<SegmentedTabOption<T>>;
  active: T;
  onChange: (key: T) => void;
  /** Many options: segments size to their label and the track scrolls sideways
   * (web's PillRow variant="scroll"). */
  scrollable?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const body = (
    <View style={[styles.track, scrollable && styles.trackScroll]}>
      {options.map((option) => {
        const isActive = option.key === active;
        return (
          <TouchableOpacity
            key={option.key}
            style={[styles.segment, scrollable && styles.segmentScroll, isActive && styles.segmentActive]}
            onPress={() => onChange(option.key)}
            activeOpacity={0.75}
          >
            {option.icon ? <View style={styles.icon}>{option.icon}</View> : null}
            <View style={styles.labelRow}>
              <AppText style={[styles.label, isActive && styles.labelActive]} numberOfLines={1}>
                {option.label}
              </AppText>
              {option.count ? (
                <View style={styles.countPill} accessibilityLabel={`${option.count} new`}>
                  <AppText style={styles.countText}>{option.count}</AppText>
                </View>
              ) : null}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
  return scrollable ? (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} accessibilityRole="tablist">
      {body}
    </ScrollView>
  ) : (
    body
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
      minHeight: 44,
      borderRadius: radii.pill,
    },
    trackScroll: { alignSelf: 'flex-start' },
    segmentScroll: { flex: 0, paddingHorizontal: 12 },
    segmentActive: {
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    icon: { marginBottom: 2 },
    labelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    countPill: { minWidth: 16, height: 16, paddingHorizontal: 4, borderRadius: radii.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent },
    countText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
    label: { fontSize: 13.5, fontWeight: '600', letterSpacing: -0.2, color: colors.textSecondary },
    // accentOnTint, not accent: this label sits directly on `segmentActive`'s
    // accentMuted fill, where light mode's plain accent falls under AA
    // contrast (color-system audit, 2026-09-25 — see theme.ts).
    labelActive: { color: colors.accentOnTint, fontWeight: '700' },
  });
}

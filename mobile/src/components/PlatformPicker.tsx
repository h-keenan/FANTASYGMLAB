import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export type LeaguePlatformKey = 'sleeper' | 'espn' | 'fleaflicker' | 'mfl';

/** Sleeper and ESPN get cards with the same treatment; the smaller platforms are quiet links below. */
const MAIN_PLATFORMS: { key: LeaguePlatformKey; label: string; monogram: string; blurb: string }[] = [
  { key: 'sleeper', label: 'Sleeper', monogram: 'S', blurb: 'Use your username' },
  { key: 'espn', label: 'ESPN', monogram: 'E', blurb: 'League ID. Public or private' },
];
const OTHER_PLATFORMS: { key: LeaguePlatformKey; label: string }[] = [
  { key: 'fleaflicker', label: 'Fleaflicker' },
  { key: 'mfl', label: 'MFL' },
];

/** Mirrors web-next's platform cards in SleeperImportForm. */
export default function PlatformPicker({
  active,
  onChange,
}: {
  active: LeaguePlatformKey;
  onChange: (platform: LeaguePlatformKey) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View>
      <View style={styles.cards} accessibilityRole="radiogroup">
        {MAIN_PLATFORMS.map((option) => {
          const selected = active === option.key;
          return (
            <TouchableOpacity
              key={option.key}
              style={[styles.card, selected && styles.cardSelected]}
              onPress={() => onChange(option.key)}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={option.label}
            >
              <View style={[styles.monogram, selected && styles.monogramSelected]}>
                <AppText style={[styles.monogramText, selected && styles.monogramTextSelected]}>{option.monogram}</AppText>
              </View>
              <AppText style={styles.cardTitle}>{option.label}</AppText>
              <AppText style={styles.cardBlurb}>{option.blurb}</AppText>
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={styles.otherRow}>
        <AppText style={styles.otherLabel}>Also:</AppText>
        {OTHER_PLATFORMS.map((option) => (
          <TouchableOpacity
            key={option.key}
            onPress={() => onChange(option.key)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={option.label}
          >
            <AppText style={[styles.otherLink, active === option.key && styles.otherLinkActive]}>{option.label}</AppText>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    cards: { flexDirection: 'row', gap: spacing.sm },
    card: {
      flex: 1,
      gap: 4,
      padding: spacing.md,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    cardSelected: { borderColor: colors.accent },
    monogram: {
      width: 28,
      height: 28,
      borderRadius: 8,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.border,
    },
    monogramSelected: { backgroundColor: colors.accent, borderColor: colors.accent },
    monogramText: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    monogramTextSelected: { color: colors.onAccent },
    cardTitle: { fontSize: 16.5, fontWeight: '700', color: colors.textPrimary },
    cardBlurb: { fontSize: 13.5, color: colors.textTertiary },
    otherRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.sm },
    otherLabel: { fontSize: 13.5, color: colors.textTertiary },
    otherLink: { fontSize: 13.5, fontWeight: '700', color: colors.textSecondary },
    otherLinkActive: { color: colors.accent },
  });
}

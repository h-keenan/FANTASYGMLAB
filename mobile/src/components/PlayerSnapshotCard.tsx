import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface SnapshotItem {
  key: string;
  label: string;
  value: string | number | null;
  /** Small contextual read under the value — e.g. "of all players" / "of
   * RBs" — describing what the rank means, never a fabricated count. */
  descriptor?: string | null;
  tone?: 'success' | 'danger' | 'neutral';
}

/**
 * The Snapshot section, consolidated into ONE cohesive card per coridian_'s
 * concept sheet — replaces the old equally-sized-tile StatGrid. Value Score
 * gets a dedicated headline slot (top-right, larger type); Overall Rank /
 * Position Rank / Age / Status / Injury Status render as a single compact
 * row underneath so it reads almost instantly instead of six separate
 * boxes. Every value is exactly what QuickViewStats/RankedPlayer already
 * compute — this component only lays it out.
 */
export default function PlayerSnapshotCard({
  valueScore,
  items,
}: {
  valueScore: string | number | null;
  items: SnapshotItem[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const toneColor = (tone?: SnapshotItem['tone']) => {
    if (tone === 'success') return colors.success;
    if (tone === 'danger') return colors.danger;
    return colors.textPrimary;
  };
  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.headerTitleRow}>
          <Ionicons name="flash-outline" size={15} color={colors.accent} style={styles.headerIcon} />
          <AppText style={styles.title}>Snapshot</AppText>
        </View>
        {valueScore !== null && valueScore !== undefined ? (
          <View style={styles.valueScoreCol}>
            <AppText style={styles.valueScoreLabel}>Value Score</AppText>
            <AppText style={styles.valueScoreValue}>{valueScore}</AppText>
          </View>
        ) : null}
      </View>
      <View style={styles.divider} />
      <View style={styles.itemsRow}>
        {items.map((item) => (
          <View key={item.key} style={styles.item}>
            <AppText style={styles.itemLabel}>{item.label}</AppText>
            <AppText style={[styles.itemValue, { color: toneColor(item.tone) }]} numberOfLines={1}>
              {item.value === null || item.value === undefined || item.value === '' ? '—' : item.value}
            </AppText>
            {item.descriptor ? (
              <AppText style={styles.itemDescriptor} numberOfLines={1}>
                {item.descriptor}
              </AppText>
            ) : null}
          </View>
        ))}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
    },
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
    headerTitleRow: { flexDirection: 'row', alignItems: 'center' },
    headerIcon: { marginRight: spacing.xs },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    valueScoreCol: { alignItems: 'flex-end' },
    valueScoreLabel: { fontSize: 11, color: colors.textSecondary },
    valueScoreValue: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.md },
    itemsRow: { flexDirection: 'row', flexWrap: 'wrap' },
    item: { minWidth: '18%', flexGrow: 1, flexBasis: '18%', paddingRight: spacing.xs, marginBottom: spacing.xs },
    itemLabel: { fontSize: 10, color: colors.textSecondary },
    itemValue: { fontSize: 17, fontWeight: '800', marginTop: 2 },
    itemDescriptor: { fontSize: 9, color: colors.textTertiary, marginTop: 1 },
  });
}

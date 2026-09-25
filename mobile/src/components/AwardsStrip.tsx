import React, { useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { PlayerAward } from '../lib/api';
import { awardTierColor, radii, spacing, type ThemeColors } from '../theme';

// Tier -> color mapping (gold/silver/bronze, with a visible neutral-accent
// fallback for untiered awards — modules/player_awards.py's tier=None case)
// lives in theme.ts as `awardTierColors`/`awardTierColorsLight` so it has a
// real light-mode counterpart: this component used to carry its own
// dark-only constant, which put gold/silver text at ~1.4:1/~1.3:1 contrast
// on a light-mode card (color-system audit, 2026-09-25).

/** Above this many awards, the horizontal strip gets a "View All" link that
 * opens the full vertical list — otherwise everything already fits in the
 * scroll and a link would be redundant chrome. */
const VIEW_ALL_THRESHOLD = 4;

function AwardDetailSheet({
  award,
  onClose,
}: {
  award: PlayerAward | null;
  onClose: () => void;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tierColor = award ? awardTierColor(award.tier, isDark, colors.accentSoft) : colors.accentSoft;
  return (
    <Modal visible={award !== null} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.sheetBackdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          {award ? (
            <>
              <View style={styles.sheetHeaderRow}>
                <View style={[styles.medal, { backgroundColor: `${tierColor}26` }]}>
                  <Ionicons name="medal" size={22} color={tierColor} />
                </View>
                <View style={styles.chipTextGroup}>
                  <AppText style={[styles.sheetTitle, { color: tierColor }]}>{award.title}</AppText>
                  {award.season ? <AppText style={styles.chipSeason}>{award.season}</AppText> : null}
                </View>
              </View>
              <AppText style={styles.sheetDescription}>{award.description}</AppText>
              {award.occurrence_count > 1 ? (
                <AppText style={styles.sheetMeta}>Earned {award.occurrence_count} times</AppText>
              ) : null}
            </>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function AwardChip({ award, onPress }: { award: PlayerAward; onPress: () => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tierColor = awardTierColor(award.tier, isDark, colors.accentSoft);
  return (
    <TouchableOpacity style={[styles.chip, { borderLeftColor: tierColor }]} onPress={onPress}>
      <View style={[styles.medal, { backgroundColor: `${tierColor}26` }]}>
        <Ionicons name="medal" size={16} color={tierColor} />
      </View>
      <View style={styles.chipTextGroup}>
        <AppText style={[styles.chipLabel, { color: tierColor }]} numberOfLines={1}>
          {award.short_label}
          {award.occurrence_count > 1 ? ` ×${award.occurrence_count}` : ''}
        </AppText>
        {award.season ? <AppText style={styles.chipSeason}>{award.season}</AppText> : null}
      </View>
    </TouchableOpacity>
  );
}

/**
 * Awards, redesigned as one compact card: a horizontal-scroll row of
 * achievement chips (icon, award, count when it recurs, season) instead of
 * the old large flex-wrap tile grid, plus a "View All" affordance once
 * there are more awards than comfortably fit in view. Same award data and
 * same tap-to-open detail sheet as before — no awards logic changed, only
 * how it's laid out.
 */
export default function AwardsStrip({ awards }: { awards: PlayerAward[] }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [selectedAward, setSelectedAward] = useState<PlayerAward | null>(null);
  const [viewAllOpen, setViewAllOpen] = useState(false);
  if (awards.length === 0) return null;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.headerTitleRow}>
          <Ionicons name="trophy-outline" size={15} color={colors.accent} style={styles.headerIcon} />
          <AppText style={styles.title}>Awards</AppText>
        </View>
        {awards.length > VIEW_ALL_THRESHOLD ? (
          <TouchableOpacity onPress={() => setViewAllOpen(true)} hitSlop={8}>
            <View style={styles.viewAllRow}>
              <AppText style={styles.viewAllText}>View All</AppText>
              <Ionicons name="chevron-forward" size={13} color={colors.accent} />
            </View>
          </TouchableOpacity>
        ) : null}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scrollRow}>
        {awards.map((award) => (
          <AwardChip key={award.badge_id} award={award} onPress={() => setSelectedAward(award)} />
        ))}
      </ScrollView>

      <AwardDetailSheet award={selectedAward} onClose={() => setSelectedAward(null)} />

      <Modal visible={viewAllOpen} transparent animationType="fade" onRequestClose={() => setViewAllOpen(false)}>
        <Pressable style={styles.sheetBackdrop} onPress={() => setViewAllOpen(false)}>
          <Pressable style={styles.listSheet} onPress={(event) => event.stopPropagation()}>
            <View style={styles.listSheetHeaderRow}>
              <AppText style={styles.sheetTitle}>All Awards</AppText>
              <TouchableOpacity onPress={() => setViewAllOpen(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.listScroll}>
              {awards.map((award) => {
                const tierColor = awardTierColor(award.tier, isDark, colors.accentSoft);
                return (
                  <TouchableOpacity
                    key={award.badge_id}
                    style={styles.listRow}
                    onPress={() => {
                      setViewAllOpen(false);
                      setSelectedAward(award);
                    }}
                  >
                    <View style={[styles.medal, { backgroundColor: `${tierColor}26` }]}>
                      <Ionicons name="medal" size={18} color={tierColor} />
                    </View>
                    <View style={styles.chipTextGroup}>
                      <AppText style={[styles.chipLabel, { color: tierColor }]}>
                        {award.short_label}
                        {award.occurrence_count > 1 ? ` ×${award.occurrence_count}` : ''}
                      </AppText>
                      {award.season ? <AppText style={styles.chipSeason}>{award.season}</AppText> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
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
      marginTop: spacing.lg,
    },
    headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
    headerTitleRow: { flexDirection: 'row', alignItems: 'center' },
    headerIcon: { marginRight: spacing.xs },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    viewAllRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
    viewAllText: { fontSize: 12, fontWeight: '700', color: colors.accent },
    scrollRow: { gap: spacing.sm, paddingRight: spacing.sm },
    chip: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderLeftWidth: 3,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.xs,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      backgroundColor: colors.background,
      maxWidth: 190,
    },
    medal: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
    chipTextGroup: { flexShrink: 1 },
    chipLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3 },
    chipSeason: { fontSize: 10, color: colors.textTertiary, fontWeight: '600', marginTop: 1 },
    sheetBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      padding: spacing.lg,
    },
    sheetHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
    sheetTitle: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    sheetDescription: { fontSize: 14, color: colors.textSecondary, lineHeight: 20 },
    sheetMeta: { fontSize: 12, color: colors.textTertiary, marginTop: spacing.sm, fontWeight: '600' },
    listSheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      padding: spacing.lg,
      maxHeight: '75%',
    },
    listSheetHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md },
    listScroll: { flexGrow: 0 },
    listRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      paddingVertical: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
  });
}

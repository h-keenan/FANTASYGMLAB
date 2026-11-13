import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import SimCrest from './SimCrest';
import SimGlyph from './SimGlyph';
import { useThemeMode } from '../context/ThemeModeContext';
import { simCompactSeason, simCompactWeek, simStatusChips } from '../lib/bottomNav';
import { requestOrbSearch } from '../lib/orbEvents';
import { simFmtRecord, type SimGame } from '../lib/simGame';
import type { SimTab } from '../lib/simGameFlow';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The phone game header: one line replacing the stacked "All games / Week /
 * Season / team" block. Back arrow to All games, "Wk 3/14 S1/5", the team as
 * a tappable chip (opens the team sheet), search (the GM sheet's search) and
 * the overflow menu (More: rules, reset week, delete). Mirrors web-next's
 * SimGameHeader; the text comes from the shared lib/bottomNav twin.
 */
export function SimGameHeader({ game, onHub, onTeam, onMore, bell }: { game: SimGame; onHub: () => void; onTeam: (teamId: string) => void; onMore: () => void; bell?: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const you = game.you;
  const season = simCompactSeason(game.dynasty);
  const showTeam = Boolean(you) && game.phase !== 'draft';
  return (
    <View style={styles.bar} testID="sim-game-header">
      <Pressable onPress={onHub} accessibilityRole="button" accessibilityLabel="Back to all games" style={styles.icon}>
        <Ionicons name="chevron-back" size={22} color={colors.textSecondary} />
      </Pressable>
      <AppText style={styles.week} numberOfLines={1} testID="game-heading">
        {simCompactWeek(game)}
        {season ? <AppText style={styles.season} testID="dynasty-progress">{` ${season}`}</AppText> : null}
      </AppText>
      {showTeam && you ? (
        <Pressable
          onPress={() => you.team_id && onTeam(you.team_id)}
          accessibilityRole="button"
          accessibilityLabel={`Your team: ${you.name}, ${simFmtRecord(you)}. Open team`}
          style={styles.chip}
          testID="sim-team-chip"
        >
          <SimCrest name={you.name} size={20} />
          <AppText style={styles.chipName} numberOfLines={1}>{you.name}</AppText>
          <AppText style={styles.chipRecord}>{simFmtRecord(you)}</AppText>
        </Pressable>
      ) : (
        <View style={styles.spacer} />
      )}
      {bell}
      <Pressable onPress={requestOrbSearch} accessibilityRole="button" accessibilityLabel="Search players and pages" style={styles.icon}>
        <Ionicons name="search-outline" size={20} color={colors.textSecondary} />
      </Pressable>
      <Pressable onPress={onMore} accessibilityRole="button" accessibilityLabel="Game menu: rules, reset week, delete" style={styles.icon}>
        <Ionicons name="ellipsis-horizontal" size={20} color={colors.textSecondary} />
      </Pressable>
    </View>
  );
}

/** The pre-advance notes as small tappable chips under the header. Each jumps to the tab that fixes it. */
export function SimStatusChips({ game, onTab }: { game: SimGame; onTab: (tab: SimTab) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const chips = simStatusChips(game.pending);
  if (chips.length === 0) return null;
  return (
    <View style={styles.chips} accessibilityLabel="Before you advance" testID="sim-status-chips">
      {chips.map((chip) => {
        const color = chip.tone === 'warning' ? colors.warning : colors.accent;
        return (
          <Pressable
            key={chip.key}
            onPress={() => onTab(chip.tab)}
            accessibilityRole="button"
            accessibilityLabel={`${chip.label}. Open ${chip.tab === 'team' ? 'Team' : 'Trades'}`}
            style={[styles.statusChip, { borderColor: color, backgroundColor: colors.glassInset }]}
          >
            <SimGlyph name={chip.tone === 'warning' ? 'alert' : 'trade'} color={color} size={14} />
            <AppText style={[styles.statusLabel, { color }]}>{chip.label}</AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    bar: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minHeight: 48 },
    icon: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
    week: { flexShrink: 0, fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    season: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    spacer: { flex: 1 },
    chip: {
      flex: 1,
      minWidth: 0,
      minHeight: 44,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
      paddingHorizontal: spacing.sm,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.glassInset,
    },
    chipName: { flexShrink: 1, fontSize: 12.5, fontWeight: '700', color: colors.textPrimary },
    chipRecord: { fontSize: 12.5, color: colors.textTertiary },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    statusChip: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minHeight: 44, paddingHorizontal: spacing.md, borderRadius: radii.pill, borderWidth: 1 },
    statusLabel: { fontSize: 12.5, fontWeight: '700' },
  });
}

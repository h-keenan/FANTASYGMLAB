import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import UsageTrendPill from '../components/UsageTrendPill';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import { api, type GmTarget, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmTargets'>;

interface TargetRow {
  target: GmTarget;
  player: RankedPlayer | null;
}

/**
 * One row of a GM Targets group — canonical PlayerIdentityRow for identity
 * (tier, opportunity classification, injury pill, same language every other
 * ranked list in the app now uses) plus a trailing value column matching
 * PlayersScreen's PlayerRankRow, and the two actions this screen owns:
 * toggling "untouchable" and removing the target. Rows sit inside one
 * continuous bordered surface with hairline dividers per group rather than
 * each being its own card (Magna Carta §12), matching PlayersScreen's
 * grouped-table treatment.
 */
function TargetGroupRow({
  row,
  isFirst,
  isLast,
  onPress,
  onToggleUntouchable,
  onRemove,
}: {
  row: TargetRow;
  isFirst: boolean;
  isLast: boolean;
  onPress: () => void;
  onToggleUntouchable: (playerId: string, next: boolean) => void;
  onRemove: (playerId: string) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { target, player } = row;
  const injury = waiverInjuryDisplay(player?.injury_status ?? null);

  return (
    <View
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
      ]}
    >
      <View style={styles.identity}>
        <PlayerIdentityRow
          playerId={target.player_id}
          name={player?.name ?? `Player ${target.player_id}`}
          position={player?.position}
          team={player?.team}
          tier={player?.tier}
          opportunityLabel={player?.opportunity_label}
          contextLine={player ? null : 'Not on the current rankings board'}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          onPress={player ? onPress : undefined}
          showDivider={false}
        />
      </View>
      <View style={styles.trailing}>
        <AppText style={styles.score}>{player?.score != null ? Math.round(player.score) : '—'}</AppText>
        <View style={styles.trailingChips}>
          <OverallRatingBadge rating={player?.overall_rating} />
          {player?.usage_trend ? <UsageTrendPill trend={player.usage_trend} /> : null}
        </View>
      </View>
      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.iconButton, target.untouchable && styles.iconButtonActive]}
          onPress={() => onToggleUntouchable(target.player_id, !target.untouchable)}
          hitSlop={8}
          accessibilityLabel={target.untouchable ? 'Remove untouchable flag' : 'Mark untouchable'}
        >
          <Ionicons
            name={target.untouchable ? 'lock-closed' : 'lock-open-outline'}
            size={15}
            color={target.untouchable ? colors.premium : colors.textSecondary}
          />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => onRemove(target.player_id)}
          hitSlop={8}
          accessibilityLabel="Remove from GM Targets"
        >
          <Ionicons name="trash-outline" size={15} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

export default function GmTargetsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'GM Targets', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [targetsResult, rankingsResult] = await Promise.all([
        api.getGmTargets(leagueId),
        api.getLeagueRankings(leagueId, { limit: 300 }),
      ]);
      const byId = new Map(rankingsResult.players.map((p) => [p.player_id, p]));
      setRows(
        targetsResult.targets.map((target) => ({
          target,
          player: byId.get(target.player_id) ?? null,
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load GM Targets.');
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const removeTarget = useCallback(
    async (playerId: string) => {
      setRows((prev) => prev.filter((row) => row.target.player_id !== playerId));
      try {
        await api.removeGmTarget(leagueId, playerId);
      } catch {
        void load();
      }
    },
    [leagueId, load],
  );

  const toggleUntouchable = useCallback(
    async (playerId: string, next: boolean) => {
      setRows((prev) =>
        prev.map((row) =>
          row.target.player_id === playerId ? { ...row, target: { ...row.target, untouchable: next } } : row,
        ),
      );
      try {
        const result = await api.setGmTargetUntouchable(leagueId, playerId, next);
        if (!result.ok) {
          void load();
        }
      } catch {
        void load();
      }
    },
    [leagueId, load],
  );

  const sorted = useMemo(
    () => [...rows].sort((a, b) => (b.target.created_at ?? '').localeCompare(a.target.created_at ?? '')),
    [rows],
  );

  // Untouchable is the one real GM decision already encoded on a target
  // (modules/gm_targets.py), so it's the natural grouping per Magna Carta
  // §4 — "who's protected from a trade" outranks "who am I just watching."
  // GM Targets itself has no server-side category/reasoning field to group
  // by beyond that; per-player "why" comes from the same RankedPlayer
  // opportunity/injury/trend signal every other list screen already
  // surfaces through PlayerIdentityRow.
  const untouchableRows = useMemo(() => sorted.filter((row) => row.target.untouchable), [sorted]);
  const watchingRows = useMemo(() => sorted.filter((row) => !row.target.untouchable), [sorted]);

  const openPlayer = useCallback(
    (row: TargetRow) => {
      if (row.player) {
        navigation.navigate('PlayerDetail', { player: row.player, leagueId, leagueName });
      }
    },
    [navigation, leagueId, leagueName],
  );

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`Players you're watching — considering buying, selling, adding, or just keeping an eye on in ${leagueName}.`}
      />

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        data={watchingRows}
        keyExtractor={(row) => row.target.player_id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        ListHeaderComponent={
          <View>
            {untouchableRows.length > 0 ? (
              <View style={styles.sectionBlock}>
                <SectionHeading title="Untouchable" icon="lock-closed" />
                {untouchableRows.map((row, index) => (
                  <TargetGroupRow
                    key={row.target.player_id}
                    row={row}
                    isFirst={index === 0}
                    isLast={index === untouchableRows.length - 1}
                    onPress={() => openPlayer(row)}
                    onToggleUntouchable={toggleUntouchable}
                    onRemove={removeTarget}
                  />
                ))}
              </View>
            ) : null}
            {watchingRows.length > 0 ? <SectionHeading title="Watching" icon="eye-outline" /> : null}
          </View>
        }
        ListEmptyComponent={
          sorted.length === 0 ? (
            <EmptyState
              icon="star-outline"
              title="No targets yet"
              subtitle='Open a player and tap "Add to GM Targets" to start watching them.'
            />
          ) : undefined
        }
        renderItem={({ item, index }) => (
          <TargetGroupRow
            row={item}
            isFirst={index === 0}
            isLast={index === watchingRows.length - 1}
            onPress={() => openPlayer(item)}
            onToggleUntouchable={toggleUntouchable}
            onRemove={removeTarget}
          />
        )}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
    listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
    sectionBlock: { marginBottom: spacing.md },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      paddingHorizontal: spacing.md,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
    },
    rowFirst: {
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopLeftRadius: radii.md,
      borderTopRightRadius: radii.md,
    },
    rowLast: {
      borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
      borderBottomLeftRadius: radii.md,
      borderBottomRightRadius: radii.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    identity: { flex: 1 },
    trailing: { alignItems: 'flex-end', gap: 3, paddingLeft: spacing.sm },
    score: { fontSize: 16, fontWeight: '700', color: colors.accent },
    trailingChips: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' },
    actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingLeft: spacing.sm },
    iconButton: {
      width: 30,
      height: 30,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      alignItems: 'center',
      justifyContent: 'center',
    },
    iconButtonActive: { borderColor: colors.premium, backgroundColor: colors.premiumMuted },
    error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}

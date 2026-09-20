import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import TierBadge from '../components/TierBadge';
import { api, type GmTarget, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmTargets'>;

interface TargetRow {
  target: GmTarget;
  player: RankedPlayer | null;
}

export default function GmTargetsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'GM Targets', leagueName);

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

  if (loading) {
    return <BrandedSpinner style={styles.center} />;
  }

  return (
    <View style={styles.container}>
      <GridBackground />
      <ScreenHero title="GM TARGETS" subtitle={leagueName} />
      <AppText style={styles.disclaimer}>
        Players you're watching — considering buying, selling, adding, or just keeping an eye on in{' '}
        {leagueName}.
      </AppText>

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        data={sorted}
        keyExtractor={(row) => row.target.player_id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        ListEmptyComponent={
          <EmptyState
            icon="star-outline"
            title="No targets yet"
            subtitle='Open a player and tap "Add to GM Targets" to start watching them.'
          />
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={StyleSheet.flatten([styles.card, item.target.untouchable ? styles.cardUntouchable : null])}
            onPress={() =>
              item.player
                ? navigation.navigate('PlayerDetail', { player: item.player, leagueId, leagueName })
                : undefined
            }
          >
            <PlayerAvatar playerId={item.target.player_id} size={40} tier={item.player?.tier} style={styles.avatar} />
            <View style={styles.nameColumn}>
              <AppText style={styles.name} numberOfLines={1}>
                {item.player?.name ?? `Player ${item.target.player_id}`}
              </AppText>
              <View style={styles.metaRow}>
                {item.player ? (
                  <>
                    <PositionBadge position={item.player.position} />
                    <AppText style={styles.meta} numberOfLines={1}>
                      {item.player.team}
                    </AppText>
                    <TierBadge storedTier={item.player.tier} />
                  </>
                ) : (
                  <AppText style={styles.meta} numberOfLines={1}>
                    Not on the current rankings board
                  </AppText>
                )}
              </View>
              {item.target.untouchable ? (
                <AppText style={styles.untouchableLabel}>Untouchable — never offered in a trade</AppText>
              ) : null}
            </View>
            <AppText style={styles.score}>
              {item.player?.score != null ? Math.round(item.player.score) : '—'}
            </AppText>
            <TouchableOpacity
              style={[styles.iconButton, item.target.untouchable ? styles.iconButtonActive : null]}
              onPress={() => toggleUntouchable(item.target.player_id, !item.target.untouchable)}
              hitSlop={8}
              accessibilityLabel={item.target.untouchable ? 'Remove untouchable flag' : 'Mark untouchable'}
            >
              <Ionicons
                name={item.target.untouchable ? 'lock-closed' : 'lock-open-outline'}
                size={16}
                color={item.target.untouchable ? colors.premium : colors.textSecondary}
              />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.removeButton}
              onPress={() => removeTarget(item.target.player_id)}
              hitSlop={8}
            >
              <AppText style={styles.removeButtonText}>Remove</AppText>
            </TouchableOpacity>
          </AnimatedCard>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md },
  cardUntouchable: { borderLeftWidth: 4, borderLeftColor: colors.premium },
  avatar: { marginRight: spacing.sm },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  untouchableLabel: { fontSize: 11, fontWeight: '600', color: colors.premium, marginTop: 3 },
  score: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginRight: spacing.sm },
  iconButton: {
    width: 30,
    height: 30,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  iconButtonActive: { borderColor: colors.premium, backgroundColor: colors.premiumMuted },
  removeButton: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  removeButtonText: { fontSize: 11, fontWeight: '600', color: colors.danger },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl, paddingHorizontal: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
});

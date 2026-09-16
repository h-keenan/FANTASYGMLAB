import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type GmTarget, type RankedPlayer } from '../lib/api';
import { resolvePlayerTier } from '../lib/playerTier';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmTargets'>;

interface TargetRow {
  target: GmTarget;
  player: RankedPlayer | null;
}

export default function GmTargetsScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: `GM Targets — ${leagueName}` });
  }, [leagueName, navigation]);

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

  useEffect(() => {
    void load();
  }, [load]);

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

  const sorted = useMemo(
    () => [...rows].sort((a, b) => (b.target.created_at ?? '').localeCompare(a.target.created_at ?? '')),
    [rows],
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.disclaimer}>
        Players you're watching — considering buying, selling, adding, or just keeping an eye on in{' '}
        {leagueName}.
      </Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={sorted}
        keyExtractor={(row) => row.target.player_id}
        contentContainerStyle={styles.listContent}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        ListEmptyComponent={
          <Text style={styles.empty}>
            No targets yet. Open a player and tap "Add to GM Targets" to start watching them.
          </Text>
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={styles.card}
            onPress={() =>
              item.player
                ? navigation.navigate('PlayerDetail', { player: item.player, leagueId, leagueName })
                : undefined
            }
          >
            <PlayerAvatar playerId={item.target.player_id} size={40} tier={item.player?.tier} style={styles.avatar} />
            <View style={styles.nameColumn}>
              <Text style={styles.name} numberOfLines={1}>
                {item.player?.name ?? `Player ${item.target.player_id}`}
              </Text>
              <Text style={styles.meta}>
                {item.player
                  ? [
                      item.player.position,
                      item.player.team,
                      item.player.tier ? resolvePlayerTier(item.player.tier).shortLabel : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')
                  : 'Not on the current rankings board'}
              </Text>
            </View>
            <Text style={styles.score}>
              {item.player?.score != null ? Math.round(item.player.score) : '—'}
            </Text>
            <TouchableOpacity
              style={styles.removeButton}
              onPress={() => removeTarget(item.target.player_id)}
              hitSlop={8}
            >
              <Text style={styles.removeButtonText}>Remove</Text>
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
  avatar: { marginRight: spacing.sm },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  score: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginRight: spacing.md },
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

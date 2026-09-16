import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type PlayerSummary, type RankedPlayer } from '../lib/api';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TeamRoster'>;

function toRankedPlayer(playerId: string, summary: PlayerSummary | undefined): RankedPlayer {
  return {
    player_id: playerId,
    name: summary?.full_name ?? null,
    position: summary?.position ?? null,
    team: summary?.team ?? null,
    age: summary?.age ?? null,
    status: summary?.status ?? null,
    injury_status: summary?.injury_status ?? null,
    tier: null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
  };
}

export default function TeamRosterScreen({ route, navigation }: Props) {
  const { ownerName, playerIds, leagueId, leagueName } = route.params;
  const [players, setPlayers] = useState<RankedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, ownerName, leagueName);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [rankingsResult, summariesById] = await Promise.all([
          api.getLeagueRankings(leagueId, { limit: 300 }),
          api.getPlayers(playerIds),
        ]);
        if (cancelled) return;

        const rankedById = new Map(rankingsResult.players.map((p) => [p.player_id, p]));
        const rows = playerIds
          .map((playerId) => rankedById.get(playerId) ?? toRankedPlayer(playerId, summariesById[playerId]))
          .filter((row) => row.name !== null || rankedById.has(row.player_id))
          .sort((a, b) => (a.position ?? '').localeCompare(b.position ?? ''));
        setPlayers(rows);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load roster.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [leagueId, playerIds]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      data={players}
      keyExtractor={(item) => item.player_id}
      contentContainerStyle={
        players.length === 0 ? styles.emptyContainer : styles.listContent
      }
      ListEmptyComponent={
        <Text style={styles.empty}>
          No player data available for this roster (Sleeper doesn't have
          records for these player ids, or the roster is empty).
        </Text>
      }
      renderItem={({ item }) => (
        <AnimatedCard
          style={styles.card}
          onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
        >
          <PlayerAvatar playerId={item.player_id} size={40} tier={item.tier} style={styles.avatar} />
          <View style={styles.positionBadge}>
            <Text style={styles.positionText}>{item.position ?? '—'}</Text>
          </View>
          <View style={styles.nameColumn}>
            <Text style={styles.name} numberOfLines={1}>
              {item.name ?? 'Unknown player'}
            </Text>
            <Text style={styles.meta}>
              {[item.team, item.status].filter(Boolean).join(' · ') || '—'}
            </Text>
          </View>
          {item.injury_status ? (
            <View style={styles.injuryPill}>
              <Text style={styles.injuryText}>{item.injury_status}</Text>
            </View>
          ) : null}
        </AnimatedCard>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { backgroundColor: colors.background },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  emptyContainer: { flex: 1, justifyContent: 'center' },
  empty: {
    textAlign: 'center',
    color: colors.textSecondary,
    paddingHorizontal: spacing.xl,
    lineHeight: 20,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
  },
  avatar: { marginRight: spacing.sm },
  positionBadge: {
    width: 34,
    height: 26,
    borderRadius: radii.sm,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  positionText: { color: colors.badgeText, fontSize: 12, fontWeight: '700' },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  injuryPill: {
    backgroundColor: colors.dangerMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  injuryText: { fontSize: 11, fontWeight: '700', color: colors.danger },
  error: { color: colors.danger, textAlign: 'center' },
});

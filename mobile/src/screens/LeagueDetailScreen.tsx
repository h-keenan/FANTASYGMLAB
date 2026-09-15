import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface TeamRow {
  rosterId: number | string;
  ownerName: string;
  playerIds: string[];
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({
      title: leagueName,
      headerRight: () => (
        <TouchableOpacity
          onPress={() => navigation.navigate('TradeCalculator', { leagueId, leagueName })}
          hitSlop={8}
        >
          <Text style={styles.headerAction}>Trade Calc</Text>
        </TouchableOpacity>
      ),
    });
  }, [leagueId, leagueName, navigation]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [usersResult, rostersResult] = await Promise.all([
          api.getLeagueUsers(leagueId),
          api.getLeagueRosters(leagueId),
        ]);
        if (cancelled) return;

        const usersById = new Map<string, string>();
        for (const user of usersResult.users) {
          const id = String(user.user_id ?? '');
          const name = String(
            user.display_name ?? user.username ?? 'Unknown owner',
          );
          if (id) usersById.set(id, name);
        }

        const rows: TeamRow[] = rostersResult.rosters.map((roster) => {
          const ownerId = String(roster.owner_id ?? '');
          const players = Array.isArray(roster.players) ? roster.players : [];
          return {
            rosterId: String(roster.roster_id ?? ''),
            ownerName: usersById.get(ownerId) ?? 'Unclaimed team',
            playerIds: players.map(String),
          };
        });
        setTeams(rows);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load league.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
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
      contentContainerStyle={styles.listContent}
      data={teams}
      keyExtractor={(item) => String(item.rosterId)}
      renderItem={({ item }) => (
        <AnimatedCard
          style={styles.card}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: item.ownerName,
              playerIds: item.playerIds,
            })
          }
        >
          <View style={styles.row}>
            <Text style={styles.owner} numberOfLines={1}>
              {item.ownerName}
            </Text>
            <View style={styles.countPill}>
              <Text style={styles.count}>{item.playerIds.length}</Text>
            </View>
          </View>
        </AnimatedCard>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { backgroundColor: colors.background },
  listContent: { padding: spacing.lg, gap: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  card: { padding: spacing.lg },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  owner: { flex: 1, fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm },
  countPill: {
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    minWidth: 28,
    alignItems: 'center',
  },
  count: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  error: { color: colors.danger, textAlign: 'center' },
  headerAction: { color: colors.accent, fontSize: 15, fontWeight: '600' },
});

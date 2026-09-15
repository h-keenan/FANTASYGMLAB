import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface TeamRow {
  rosterId: number | string;
  ownerName: string;
  playerCount: number;
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: leagueName });
  }, [leagueName, navigation]);

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
            playerCount: players.length,
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
    <View style={styles.container}>
      <Text style={styles.note}>
        Team rosters shown by player count only — full player-level detail
        (names, positions, values) needs a players endpoint not built yet.
      </Text>
      <FlatList
        data={teams}
        keyExtractor={(item) => String(item.rosterId)}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.owner}>{item.ownerName}</Text>
            <Text style={styles.count}>{item.playerCount} players</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  note: {
    fontSize: 12,
    color: '#6b7280',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#f9fafb',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e5e7eb',
  },
  owner: { fontSize: 16 },
  count: { fontSize: 14, color: '#6b7280' },
  error: { color: '#dc2626', textAlign: 'center' },
});

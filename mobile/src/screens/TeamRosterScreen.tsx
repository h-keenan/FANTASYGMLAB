import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { api, type PlayerSummary } from '../lib/api';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TeamRoster'>;

interface RosterRow extends PlayerSummary {
  playerId: string;
}

export default function TeamRosterScreen({ route, navigation }: Props) {
  const { ownerName, playerIds } = route.params;
  const [players, setPlayers] = useState<RosterRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: ownerName });
  }, [ownerName, navigation]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const byId = await api.getPlayers(playerIds);
        if (cancelled) return;
        const rows = playerIds
          .map((playerId) => {
            const player = byId[playerId];
            return player ? { ...player, playerId } : null;
          })
          .filter((row): row is RosterRow => row !== null)
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
  }, [playerIds]);

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
      data={players}
      keyExtractor={(item) => item.playerId}
      contentContainerStyle={players.length === 0 ? styles.emptyContainer : undefined}
      ListEmptyComponent={
        <Text style={styles.empty}>
          No player data available for this roster (Sleeper doesn't have
          records for these player ids, or the roster is empty).
        </Text>
      }
      renderItem={({ item }) => (
        <View style={styles.row}>
          <View style={styles.positionBadge}>
            <Text style={styles.positionText}>{item.position ?? '—'}</Text>
          </View>
          <View style={styles.nameColumn}>
            <Text style={styles.name}>{item.full_name ?? 'Unknown player'}</Text>
            <Text style={styles.meta}>
              {[item.team, item.status].filter(Boolean).join(' · ') || '—'}
            </Text>
          </View>
          {item.injury_status ? (
            <Text style={styles.injury}>{item.injury_status}</Text>
          ) : null}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  emptyContainer: { flex: 1, justifyContent: 'center' },
  empty: {
    textAlign: 'center',
    color: '#6b7280',
    paddingHorizontal: 24,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e5e7eb',
  },
  positionBadge: {
    width: 40,
    height: 28,
    borderRadius: 6,
    backgroundColor: '#111827',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  positionText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  nameColumn: { flex: 1 },
  name: { fontSize: 15, fontWeight: '600' },
  meta: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  injury: { fontSize: 12, color: '#dc2626', fontWeight: '600' },
  error: { color: '#dc2626', textAlign: 'center' },
});

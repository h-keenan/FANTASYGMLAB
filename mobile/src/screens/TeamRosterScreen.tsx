import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { api, type PlayerSummary } from '../lib/api';
import { cardShadow, colors, radii, spacing } from '../theme';
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
      keyExtractor={(item) => item.playerId}
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
        <View style={styles.card}>
          <View style={styles.positionBadge}>
            <Text style={styles.positionText}>{item.position ?? '—'}</Text>
          </View>
          <View style={styles.nameColumn}>
            <Text style={styles.name} numberOfLines={1}>
              {item.full_name ?? 'Unknown player'}
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
        </View>
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
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    ...cardShadow,
  },
  positionBadge: {
    width: 40,
    height: 32,
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

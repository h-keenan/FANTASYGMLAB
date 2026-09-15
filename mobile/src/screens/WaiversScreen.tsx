import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api, type RankedPlayer } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Waivers'>;

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];

export default function WaiversScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [freeAgents, setFreeAgents] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState('ALL');
  const [search, setSearch] = useState('');

  useEffect(() => {
    navigation.setOptions({ title: `Waivers — ${leagueName}` });
  }, [leagueName, navigation]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [rankings, rosters] = await Promise.all([
          api.getLeagueRankings(leagueId, { lens: 'Dynasty', limit: 300 }),
          api.getLeagueRosters(leagueId),
        ]);
        if (cancelled) return;

        const rosteredIds = new Set<string>();
        for (const roster of rosters.rosters) {
          const players = Array.isArray(roster.players) ? roster.players : [];
          for (const id of players) rosteredIds.add(String(id));
        }

        const available = rankings.players
          .filter((p) => !rosteredIds.has(p.player_id))
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
        setFreeAgents(available);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load waivers.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const filtered = useMemo(() => {
    if (!freeAgents) return [];
    const query = search.trim().toLowerCase();
    return freeAgents
      .filter((p) => position === 'ALL' || p.position === position)
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [freeAgents, position, search]);

  return (
    <View style={styles.container}>
      <Text style={styles.disclaimer}>
        Best available free agents — nobody's roster in this league has them. Ranked by raw
        value, not yet tailored to your specific team needs.
      </Text>

      <TextInput
        style={styles.searchInput}
        placeholder="Search free agents"
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
      />
      <View style={styles.filterRow}>
        {POSITIONS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, position === option && styles.pillActive]}
            onPress={() => setPosition(option)}
          >
            <Text style={[styles.pillText, position === option && styles.pillTextActive]}>{option}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {loading ? (
        <ActivityIndicator style={styles.loading} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item, index }) => (
            <AnimatedCard
              style={styles.card}
              onPress={() => navigation.navigate('PlayerDetail', { player: item })}
            >
              <View style={styles.rankBadge}>
                <Text style={styles.rankText}>{index + 1}</Text>
              </View>
              <View style={styles.nameColumn}>
                <Text style={styles.name} numberOfLines={1}>
                  {item.name ?? 'Unknown'}
                </Text>
                <Text style={styles.meta}>
                  {[item.position, item.team, item.tier].filter(Boolean).join(' · ')}
                </Text>
              </View>
              <Text style={styles.score}>{item.score != null ? Math.round(item.score) : '—'}</Text>
            </AnimatedCard>
          )}
          ListEmptyComponent={<Text style={styles.empty}>No free agents match.</Text>}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  searchInput: {
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    marginBottom: spacing.sm,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff' },
  loading: { marginTop: spacing.xl },
  listContent: { padding: spacing.lg, paddingTop: 0, gap: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md },
  rankBadge: {
    width: 36,
    height: 32,
    borderRadius: radii.sm,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  rankText: { color: colors.badgeText, fontSize: 12, fontWeight: '700' },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  score: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
});

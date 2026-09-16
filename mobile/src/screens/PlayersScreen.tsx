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
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type RankedPlayer, type ValuationLens } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Players'>;

const LENSES: ValuationLens[] = ['Dynasty', 'Rebuild', 'Non-Dynasty'];
const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];

export default function PlayersScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [lens, setLens] = useState<ValuationLens>('Dynasty');
  const [position, setPosition] = useState('ALL');
  const [search, setSearch] = useState('');
  const [players, setPlayers] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: `Players — ${leagueName}` });
  }, [leagueName, navigation]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const result = await api.getLeagueRankings(leagueId, { lens, limit: 300 });
        if (!cancelled) setPlayers(result.players);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load players.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens]);

  const filtered = useMemo(() => {
    if (!players) return [];
    const query = search.trim().toLowerCase();
    return players
      .filter((p) => position === 'ALL' || p.position === position)
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [players, position, search]);

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search players"
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
        placeholderTextColor={colors.textTertiary}
      />

      <View style={styles.filterRow}>
        {LENSES.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, lens === option && styles.pillActive]}
            onPress={() => setLens(option)}
          >
            <Text style={[styles.pillText, lens === option && styles.pillTextActive]}>{option}</Text>
          </TouchableOpacity>
        ))}
      </View>
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
        <ActivityIndicator style={styles.loading} color={colors.accent} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <AnimatedCard
              style={styles.card}
              onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
            >
              <PlayerAvatar playerId={item.player_id} size={40} tier={item.tier} style={styles.avatar} />
              <View style={styles.rankBadge}>
                <Text style={styles.rankText}>{item.overall_rank ?? '—'}</Text>
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
          ListEmptyComponent={<Text style={styles.empty}>No players match.</Text>}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  searchInput: {
    marginHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
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
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md },
  avatar: { marginRight: spacing.sm },
  rankBadge: {
    width: 30,
    height: 26,
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

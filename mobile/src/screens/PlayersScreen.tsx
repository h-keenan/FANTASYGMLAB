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
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import TierBadge from '../components/TierBadge';
import { api, type RankedPlayer, type ValuationLens } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Players'>;

const LENSES: ValuationLens[] = ['Dynasty', 'Rebuild', 'Non-Dynasty'];
const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];
const AGE_FILTERS = ['ALL', 'Under 25', '25-28', '29+'] as const;
const STATUS_FILTERS = ['ALL', 'Active', 'Inactive'] as const;
const AVAILABILITY_FILTERS = ['ALL', 'Healthy', 'Injured'] as const;

type AgeFilter = (typeof AGE_FILTERS)[number];
type StatusFilter = (typeof STATUS_FILTERS)[number];
type AvailabilityFilter = (typeof AVAILABILITY_FILTERS)[number];

function matchesAge(age: number | null, filter: AgeFilter): boolean {
  if (filter === 'ALL') return true;
  if (age == null) return false;
  if (filter === 'Under 25') return age < 25;
  if (filter === '25-28') return age >= 25 && age <= 28;
  return age >= 29;
}

function matchesStatus(status: string | null, filter: StatusFilter): boolean {
  if (filter === 'ALL') return true;
  const normalized = (status ?? '').trim().toLowerCase();
  return filter === 'Active' ? normalized === 'active' : normalized !== 'active' && normalized !== '';
}

function matchesAvailability(injuryStatus: string | null, filter: AvailabilityFilter): boolean {
  if (filter === 'ALL') return true;
  const hasInjury = Boolean((injuryStatus ?? '').trim());
  return filter === 'Injured' ? hasInjury : !hasInjury;
}

export default function PlayersScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [lens, setLens] = useState<ValuationLens>('Dynasty');
  const [position, setPosition] = useState('ALL');
  const [ageFilter, setAgeFilter] = useState<AgeFilter>('ALL');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityFilter>('ALL');
  const [search, setSearch] = useState('');
  const [players, setPlayers] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Players', leagueName);

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
      .filter((p) => matchesAge(p.age, ageFilter))
      .filter((p) => matchesStatus(p.status, statusFilter))
      .filter((p) => matchesAvailability(p.injury_status, availabilityFilter))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [players, position, ageFilter, statusFilter, availabilityFilter, search]);

  return (
    <View style={styles.container}>
      <GridBackground />
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
      <View style={styles.filterRow}>
        {AGE_FILTERS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, ageFilter === option && styles.pillActive]}
            onPress={() => setAgeFilter(option)}
          >
            <Text style={[styles.pillText, ageFilter === option && styles.pillTextActive]}>{option}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.filterRow}>
        {STATUS_FILTERS.map((option) => (
          <TouchableOpacity
            key={`status-${option}`}
            style={[styles.pill, statusFilter === option && styles.pillActive]}
            onPress={() => setStatusFilter(option)}
          >
            <Text style={[styles.pillText, statusFilter === option && styles.pillTextActive]}>{option}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.filterRow}>
        {AVAILABILITY_FILTERS.map((option) => (
          <TouchableOpacity
            key={`availability-${option}`}
            style={[styles.pill, availabilityFilter === option && styles.pillActive]}
            onPress={() => setAvailabilityFilter(option)}
          >
            <Text style={[styles.pillText, availabilityFilter === option && styles.pillTextActive]}>{option}</Text>
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
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
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
                <View style={styles.metaRow}>
                  <Text style={styles.meta} numberOfLines={1}>
                    {[item.position, item.team, item.opportunity_label].filter(Boolean).join(' · ')}
                  </Text>
                  <TierBadge storedTier={item.tier} />
                </View>
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
  pillActive: { backgroundColor: 'transparent', borderColor: colors.accent, borderWidth: 1.5 },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: colors.accent, fontWeight: '700' },
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
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  score: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
});

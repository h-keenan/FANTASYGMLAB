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
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import TierBadge from '../components/TierBadge';
import { api, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Waivers'>;

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];

const INJURY_RISK_STATUSES = new Set(['out', 'ir', 'doubtful', 'pup', 'suspended']);
const INJURY_WATCH_STATUSES = new Set(['questionable', 'sus']);

function injuryPillColor(status: string | null): string | null {
  const normalized = (status ?? '').trim().toLowerCase();
  if (!normalized) return null;
  if (INJURY_RISK_STATUSES.has(normalized)) return colors.danger;
  if (INJURY_WATCH_STATUSES.has(normalized)) return colors.premium;
  return null;
}

export default function WaiversScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [freeAgents, setFreeAgents] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState('ALL');
  const [search, setSearch] = useState('');

  useScreenHeaderTitle(navigation, 'Waivers', leagueName);

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
      <GridBackground />
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
        placeholderTextColor={colors.textTertiary}
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
        <ActivityIndicator style={styles.loading} color={colors.accent} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          renderItem={({ item, index }) => (
            <WaiverCard
              player={item}
              rank={index + 1}
              onPress={() => navigation.navigate('PlayerDetail', { player: item, leagueId, leagueName })}
            />
          )}
          ListEmptyComponent={<Text style={styles.empty}>No free agents match.</Text>}
        />
      )}
    </View>
  );
}

function WaiverCard({
  player,
  rank,
  onPress,
}: {
  player: RankedPlayer;
  rank: number;
  onPress: () => void;
}) {
  const injuryColor = injuryPillColor(player.injury_status);
  return (
    <AnimatedCard style={styles.card} onPress={onPress}>
      <View style={styles.cardTopRow}>
        <View style={styles.avatarWrap}>
          <PlayerAvatar playerId={player.player_id} size={44} tier={player.tier} />
          <View style={styles.rankBadge}>
            <Text style={styles.rankText}>{rank}</Text>
          </View>
        </View>
        <View style={styles.nameColumn}>
          <Text style={styles.name} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </Text>
          <View style={styles.metaRow}>
            <Text style={styles.meta}>
              {[player.position, player.team].filter(Boolean).join(' · ')}
            </Text>
            {player.position_rank ? (
              <View style={styles.positionRankPill}>
                <Text style={styles.positionRankText}>
                  {player.position}{player.position_rank}
                </Text>
              </View>
            ) : null}
          </View>
          {injuryColor ? (
            <View style={styles.injuryRow}>
              <Ionicons name="medkit-outline" size={11} color={injuryColor} />
              <Text style={[styles.injuryText, { color: injuryColor }]}>{player.injury_status}</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.valueColumn}>
          <Text style={styles.valueNumber}>{player.score != null ? Math.round(player.score) : '—'}</Text>
          <Text style={styles.valueLabel}>VALUE</Text>
          <TierBadge storedTier={player.tier} />
        </View>
      </View>
    </AnimatedCard>
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
  card: { padding: spacing.md },
  cardTopRow: { flexDirection: 'row', alignItems: 'center' },
  avatarWrap: { marginRight: spacing.md },
  rankBadge: {
    position: 'absolute',
    top: -4,
    left: -4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.badgeBackground,
    borderWidth: 2,
    borderColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: { color: colors.badgeText, fontSize: 10, fontWeight: '700' },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  positionRankPill: {
    backgroundColor: colors.border,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  injuryRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  injuryText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  valueColumn: { alignItems: 'flex-end', gap: 2 },
  valueNumber: { fontSize: 18, fontWeight: '700', color: colors.accent },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
});

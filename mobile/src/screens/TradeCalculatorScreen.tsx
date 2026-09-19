import React, { useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import { api, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { valueDirectionLabel } from '../lib/tradeValue';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeCalculator'>;
type Side = 'A' | 'B';

const MAX_SEARCH_RESULTS = 40;
const POSITION_FILTERS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

function playerScore(player: RankedPlayer): number {
  return typeof player.score === 'number' ? player.score : 0;
}

export default function TradeCalculatorScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [rankings, setRankings] = useState<RankedPlayer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sideA, setSideA] = useState<RankedPlayer[]>([]);
  const [sideB, setSideB] = useState<RankedPlayer[]>([]);
  const [activeSide, setActiveSide] = useState<Side>('A');
  const [search, setSearch] = useState('');
  const [positionFilter, setPositionFilter] = useState<string | null>(null);

  const orbClearance = useOrbClearance();

  useScreenHeaderTitle(navigation, 'Trade Calculator', leagueName);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.getLeagueRankings(leagueId, { lens: 'Dynasty', limit: 300 });
        if (!cancelled) setRankings(result.players);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load player values.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const selectedIds = useMemo(
    () => new Set([...sideA, ...sideB].map((p) => p.player_id)),
    [sideA, sideB],
  );

  const searchResults = useMemo(() => {
    if (!rankings) return [];
    const query = search.trim().toLowerCase();
    return rankings
      .filter((p) => !selectedIds.has(p.player_id))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query))
      .filter((p) => !positionFilter || (p.position ?? '').toUpperCase() === positionFilter)
      .slice(0, MAX_SEARCH_RESULTS);
  }, [rankings, selectedIds, search, positionFilter]);

  const totalA = useMemo(() => sideA.reduce((sum, p) => sum + playerScore(p), 0), [sideA]);
  const totalB = useMemo(() => sideB.reduce((sum, p) => sum + playerScore(p), 0), [sideB]);
  const delta = totalB - totalA;

  const addToActiveSide = (player: RankedPlayer) => {
    if (activeSide === 'A') {
      setSideA((prev) => [...prev, player]);
    } else {
      setSideB((prev) => [...prev, player]);
    }
  };

  const removeFromSide = (side: Side, playerId: string) => {
    if (side === 'A') {
      setSideA((prev) => prev.filter((p) => p.player_id !== playerId));
    } else {
      setSideB((prev) => prev.filter((p) => p.player_id !== playerId));
    }
  };

  if (loading) {
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <GridBackground />
      <AppText style={styles.disclaimer}>
        Raw asset value only — {leagueName}'s {'“'}Dynasty{'”'} valuations. Doesn't yet
        weigh roster fit or strategy, unlike the full web Trade Analyzer.
      </AppText>

      <View style={styles.sidesRow}>
        <TradeSide
          label="You Send"
          players={sideA}
          total={totalA}
          active={activeSide === 'A'}
          onPressHeader={() => setActiveSide('A')}
          onRemove={(id) => removeFromSide('A', id)}
        />
        <TradeSide
          label="You Receive"
          players={sideB}
          total={totalB}
          active={activeSide === 'B'}
          onPressHeader={() => setActiveSide('B')}
          onRemove={(id) => removeFromSide('B', id)}
        />
      </View>

      {sideA.length > 0 || sideB.length > 0 ? (
        <AppText style={styles.deltaLabel}>{valueDirectionLabel(delta)}</AppText>
      ) : null}

      <View style={styles.positionRow}>
        <TouchableOpacity
          style={[styles.pill, positionFilter === null && styles.pillActive]}
          onPress={() => setPositionFilter(null)}
        >
          <AppText style={[styles.pillText, positionFilter === null && styles.pillTextActive]}>All</AppText>
        </TouchableOpacity>
        {POSITION_FILTERS.map((position) => (
          <TouchableOpacity
            key={position}
            style={[styles.pill, positionFilter === position && styles.pillActive]}
            onPress={() => setPositionFilter(positionFilter === position ? null : position)}
          >
            <AppText style={[styles.pillText, positionFilter === position && styles.pillTextActive]}>{position}</AppText>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.searchInput}
        placeholder={`Search players to add to ${activeSide === 'A' ? 'You Send' : 'You Receive'}`}
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
        placeholderTextColor={colors.textTertiary}
      />

      <FlatList
        data={searchResults}
        keyExtractor={(item) => item.player_id}
        contentContainerStyle={[styles.resultsList, { paddingBottom: orbClearance }]}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.resultRow} onPress={() => addToActiveSide(item)}>
            <PlayerAvatar playerId={item.player_id} size={36} tier={item.tier} style={styles.resultAvatar} />
            <View style={styles.resultInfo}>
              <AppText style={styles.resultName} numberOfLines={1}>
                {item.name ?? 'Unknown'}
              </AppText>
              <View style={styles.resultMetaRow}>
                <PositionBadge position={item.position} />
                <AppText style={styles.resultMeta}>{item.team}</AppText>
              </View>
            </View>
            <AppText style={styles.resultScore}>{Math.round(playerScore(item))}</AppText>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <AppText style={styles.empty}>
            {search ? 'No matching players.' : 'Start typing to search players.'}
          </AppText>
        }
      />
    </KeyboardAvoidingView>
  );
}

function TradeSide({
  label,
  players,
  total,
  active,
  onPressHeader,
  onRemove,
}: {
  label: string;
  players: RankedPlayer[];
  total: number;
  active: boolean;
  onPressHeader: () => void;
  onRemove: (playerId: string) => void;
}) {
  return (
    <View style={[styles.side, active && styles.sideActive]}>
      <TouchableOpacity onPress={onPressHeader}>
        <AppText style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</AppText>
        <AppText style={styles.sideTotal}>{Math.round(total)}</AppText>
      </TouchableOpacity>
      {players.map((player) => (
        <TouchableOpacity
          key={player.player_id}
          style={styles.chip}
          onPress={() => onRemove(player.player_id)}
        >
          <AppText style={styles.chipText} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </AppText>
          <AppText style={styles.chipRemove}>{'×'}</AppText>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: spacing.md,
    lineHeight: 16,
  },
  sidesRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  side: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: 'transparent',
    padding: spacing.md,
    minHeight: 96,
  },
  sideActive: { borderColor: colors.accent },
  sideLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  sideLabelActive: { color: colors.accent },
  sideTotal: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    marginBottom: spacing.xs,
  },
  chipText: { flex: 1, fontSize: 13, color: colors.textPrimary, marginRight: spacing.xs },
  chipRemove: { fontSize: 14, color: colors.textSecondary, fontWeight: '700' },
  deltaLabel: {
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  positionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
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
  pillTextActive: { color: '#fff', fontWeight: '700' },
  searchInput: {
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
  resultsList: { paddingBottom: spacing.xl },
  resultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  resultAvatar: { marginRight: spacing.sm },
  resultInfo: { flex: 1, marginRight: spacing.sm },
  resultName: { fontSize: 15, fontWeight: '500', color: colors.textPrimary },
  resultMeta: { fontSize: 12, color: colors.textSecondary },
  resultMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  resultScore: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center' },
});

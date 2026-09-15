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

import { api, type RankedPlayer } from '../lib/api';
import { valueDirectionLabel } from '../lib/tradeValue';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeCalculator'>;
type Side = 'A' | 'B';

const MAX_SEARCH_RESULTS = 40;

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

  useEffect(() => {
    navigation.setOptions({ title: `Trade Calculator` });
  }, [navigation]);

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
      .slice(0, MAX_SEARCH_RESULTS);
  }, [rankings, selectedIds, search]);

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
      <Text style={styles.disclaimer}>
        Raw asset value only — {leagueName}'s {'“'}Dynasty{'”'} valuations. Doesn't yet
        weigh roster fit or strategy, unlike the full web Trade Analyzer.
      </Text>

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
        <Text style={styles.deltaLabel}>{valueDirectionLabel(delta)}</Text>
      ) : null}

      <TextInput
        style={styles.searchInput}
        placeholder={`Search players to add to ${activeSide === 'A' ? 'You Send' : 'You Receive'}`}
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
      />

      <FlatList
        data={searchResults}
        keyExtractor={(item) => item.player_id}
        contentContainerStyle={styles.resultsList}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.resultRow} onPress={() => addToActiveSide(item)}>
            <View style={styles.resultInfo}>
              <Text style={styles.resultName} numberOfLines={1}>
                {item.name ?? 'Unknown'}
              </Text>
              <Text style={styles.resultMeta}>
                {[item.position, item.team].filter(Boolean).join(' · ')}
              </Text>
            </View>
            <Text style={styles.resultScore}>{Math.round(playerScore(item))}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {search ? 'No matching players.' : 'Start typing to search players.'}
          </Text>
        }
      />
    </View>
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
        <Text style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</Text>
        <Text style={styles.sideTotal}>{Math.round(total)}</Text>
      </TouchableOpacity>
      {players.map((player) => (
        <TouchableOpacity
          key={player.player_id}
          style={styles.chip}
          onPress={() => onRemove(player.player_id)}
        >
          <Text style={styles.chipText} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </Text>
          <Text style={styles.chipRemove}>{'×'}</Text>
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
  searchInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
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
  resultInfo: { flex: 1, marginRight: spacing.sm },
  resultName: { fontSize: 15, fontWeight: '500', color: colors.textPrimary },
  resultMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  resultScore: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center' },
});

import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import { api, type QuickViewModel, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'PlayerCompare'>;

interface CompareSide {
  player: RankedPlayer;
  overallRating: number | null;
  model: QuickViewModel | null;
}

/** One head-to-head row: label, both sides' real values, and which side
 * (if either) reads higher. Never a synthesized "winner" score — just
 * highlights whichever real number is bigger, or neither when they tie or
 * either side is missing. */
interface CompareRow {
  label: string;
  a: number | null;
  b: number | null;
  format?: (value: number) => string;
}

function buildRows(a: CompareSide, b: CompareSide): CompareRow[] {
  return [
    { label: 'Overall', a: a.overallRating, b: b.overallRating },
    { label: 'Value Score', a: a.player.score, b: b.player.score, format: (v) => Math.round(v).toLocaleString() },
    {
      label: 'Position Rank',
      a: a.player.position_rank,
      b: b.player.position_rank,
      // Lower is better for rank — flip the compare direction below via negation.
      format: (v) => `#${v}`,
    },
    { label: 'Age', a: a.player.age, b: b.player.age },
    { label: 'Market', a: a.model?.market_score ?? null, b: b.model?.market_score ?? null, format: (v) => Math.round(v).toString() },
    {
      label: 'Opportunity',
      a: a.model?.opportunity_score ?? null,
      b: b.model?.opportunity_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    {
      label: 'Scarcity',
      a: a.model?.scarcity_score ?? null,
      b: b.model?.scarcity_score ?? null,
      format: (v) => Math.round(v).toString(),
    },
    { label: 'Role', a: a.model?.role_score ?? null, b: b.model?.role_score ?? null, format: (v) => Math.round(v).toString() },
  ];
}

const LOWER_IS_BETTER = new Set(['Position Rank']);

function CompareRowView({ row }: { row: CompareRow }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const lowerIsBetter = LOWER_IS_BETTER.has(row.label);
  const hasBoth = row.a !== null && row.b !== null;
  const aWins = hasBoth && row.a !== row.b && (lowerIsBetter ? row.a! < row.b! : row.a! > row.b!);
  const bWins = hasBoth && row.a !== row.b && (lowerIsBetter ? row.b! < row.a! : row.b! > row.a!);
  const display = (value: number | null) => (value === null ? '—' : row.format ? row.format(value) : String(value));
  return (
    <View style={styles.row}>
      <AppText style={[styles.rowValue, aWins && styles.rowValueWin]}>{display(row.a)}</AppText>
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      <AppText style={[styles.rowValue, bWins && styles.rowValueWin]}>{display(row.b)}</AppText>
    </View>
  );
}

function IdentityHeader({ side, align }: { side: RankedPlayer; align: 'left' | 'right' }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.identity, align === 'right' && styles.identityRight]}>
      <PlayerAvatar playerId={side.player_id} size={56} tier={side.tier} />
      <AppText style={styles.identityName} numberOfLines={2}>
        {side.name ?? 'Unknown'}
      </AppText>
      <View style={styles.identityMetaRow}>
        <PositionBadge position={side.position} />
        {side.team ? (
          <AppText style={styles.identityMeta} numberOfLines={1}>
            {side.team}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

export default function PlayerCompareScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player, leagueId, leagueName } = route.params;
  const [search, setSearch] = useState('');
  const [candidates, setCandidates] = useState<RankedPlayer[] | null>(null);
  const [playerB, setPlayerB] = useState<RankedPlayer | null>(null);
  const [sides, setSides] = useState<[CompareSide, CompareSide] | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  useScreenHeaderTitle(navigation, 'Compare', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueRankings(leagueId, { limit: 300 })
      .then((result) => {
        if (!cancelled) setCandidates(result.players.filter((p) => p.player_id !== player.player_id));
      })
      .catch(() => {
        if (!cancelled) setCandidates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, player.player_id]);

  useEffect(() => {
    if (!playerB) {
      setSides(null);
      return;
    }
    let cancelled = false;
    setLoadingCompare(true);
    Promise.all([api.getPlayerQuickView(player.player_id), api.getPlayerQuickView(playerB.player_id)])
      .then(([a, b]) => {
        if (cancelled) return;
        setSides([
          { player, overallRating: a.stats?.overall_rating ?? null, model: a.model },
          { player: playerB, overallRating: b.stats?.overall_rating ?? null, model: b.model },
        ]);
      })
      .catch(() => {
        if (!cancelled) setSides(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingCompare(false);
      });
    return () => {
      cancelled = true;
    };
  }, [player, playerB]);

  const filteredCandidates = useMemo(() => {
    if (!candidates) return [];
    const query = search.trim().toLowerCase();
    if (!query) return candidates.slice(0, 50);
    return candidates.filter((p) => (p.name ?? '').toLowerCase().includes(query)).slice(0, 50);
  }, [candidates, search]);

  if (!playerB) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <View style={styles.pickerHeader}>
          <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} />
          <AppText style={styles.pickerHeaderText}>Compare {player.name ?? 'this player'} against —</AppText>
        </View>
        <TextInput
          style={styles.searchInput}
          placeholder="Search for a player to compare"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          placeholderTextColor={colors.textTertiary}
        />
        {candidates === null ? (
          <BrandedSpinner style={styles.center} />
        ) : (
          <FlatList
            data={filteredCandidates}
            keyExtractor={(item) => item.player_id}
            contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
            ListEmptyComponent={<AppText style={styles.empty}>No players match.</AppText>}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.candidateRow} onPress={() => setPlayerB(item)}>
                <PlayerAvatar playerId={item.player_id} size={36} tier={item.tier} style={styles.candidateAvatar} />
                <View style={styles.candidateTextGroup}>
                  <AppText style={styles.candidateName} numberOfLines={1}>
                    {item.name ?? 'Unknown'}
                  </AppText>
                  <View style={styles.candidateMetaRow}>
                    <PositionBadge position={item.position} />
                    <AppText style={styles.candidateMeta}>{item.team}</AppText>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
            )}
          />
        )}
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <TouchableOpacity style={styles.changeButton} onPress={() => setPlayerB(null)}>
        <Ionicons name="swap-horizontal-outline" size={14} color={colors.accent} />
        <AppText style={styles.changeButtonText}>Compare someone else</AppText>
      </TouchableOpacity>
      {loadingCompare || !sides ? (
        <BrandedSpinner style={styles.center} />
      ) : (
        <View style={[styles.card, { marginBottom: orbClearance }]}>
          <View style={styles.identityRow}>
            <IdentityHeader side={sides[0].player} align="left" />
            <AppText style={styles.vsLabel}>VS</AppText>
            <IdentityHeader side={sides[1].player} align="right" />
          </View>
          <AnimatedCard style={styles.tableCard}>
            {buildRows(sides[0], sides[1]).map((row) => (
              <CompareRowView key={row.label} row={row} />
            ))}
          </AnimatedCard>
        </View>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  pickerHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: spacing.lg, paddingBottom: spacing.sm },
  pickerHeaderText: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  searchInput: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
  },
  listContent: { paddingHorizontal: spacing.lg, gap: spacing.xs },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  candidateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  candidateAvatar: {},
  candidateTextGroup: { flex: 1 },
  candidateName: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  candidateMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  candidateMeta: { fontSize: 11, color: colors.textSecondary },
  changeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    alignSelf: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.accentMuted,
  },
  changeButtonText: { fontSize: 12, fontWeight: '600', color: colors.accent },
  card: { paddingHorizontal: spacing.lg },
  identityRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.md },
  identity: { flex: 1, alignItems: 'center', gap: spacing.xs },
  identityRight: {},
  identityName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  identityMeta: { fontSize: 11, color: colors.textSecondary },
  vsLabel: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, marginTop: spacing.lg },
  tableCard: { padding: spacing.md, gap: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  rowLabel: { flex: 1, fontSize: 12, color: colors.textSecondary, textAlign: 'center' },
  rowValue: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  rowValueWin: { color: colors.successBright },
  });
}

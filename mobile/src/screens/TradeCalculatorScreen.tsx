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
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { valueDirectionLabel } from '../lib/tradeValue';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeCalculator'>;
type Side = 'A' | 'B';

const MAX_SEARCH_RESULTS = 40;
const POSITION_FILTERS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

function playerScore(player: RankedPlayer): number {
  return typeof player.score === 'number' ? player.score : 0;
}

export default function TradeCalculatorScreen({ route, navigation }: Props) {
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { lens } = useValuationLens(leagueId);
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
    (async () => {
      try {
        const result = await api.getLeagueRankings(leagueId, { lens, limit: 300 });
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
  }, [leagueId, lens]);

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
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={[styles.container, { paddingTop: headerHeight }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`Raw asset value only — ${leagueName}'s “Dynasty” valuations. Doesn't yet weigh roster fit or strategy, unlike the full web Trade Analyzer.`}
      />

      <View style={styles.sidesRow}>
        <TradeSide
          label="You Send"
          dotColor={colors.danger}
          players={sideA}
          total={totalA}
          active={activeSide === 'A'}
          onPressHeader={() => setActiveSide('A')}
          onRemove={(id) => removeFromSide('A', id)}
        />
        <TradeSide
          label="You Receive"
          dotColor={colors.successBright}
          players={sideB}
          total={totalB}
          active={activeSide === 'B'}
          onPressHeader={() => setActiveSide('B')}
          onRemove={(id) => removeFromSide('B', id)}
        />
      </View>

      {sideA.length > 0 || sideB.length > 0 ? (
        <>
          <AppText style={styles.deltaLabel}>{valueDirectionLabel(delta)}</AppText>
          <ValueSplitBar totalA={totalA} totalB={totalB} />
        </>
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
        renderItem={({ item, index }) => (
          <PlayerIdentityRow
            playerId={item.player_id}
            name={item.name}
            position={item.position}
            team={item.team}
            tier={item.tier}
            trailingValue={String(Math.round(playerScore(item)))}
            onPress={() => addToActiveSide(item)}
            showDivider={index < searchResults.length - 1}
          />
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

/** A visual read of the two sides' totals under the plain "Slight value edge
 * to Side A"-style text — coridian_: "this visually looks bad should have a
 * value bar graph under." Same split-bar pattern MatchupScreen already uses
 * for "your lineup vs. their lineup." */
function ValueSplitBar({ totalA, totalB }: { totalA: number; totalB: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const total = totalA + totalB;
  const shareA = total > 0 ? Math.max(0.05, Math.min(0.95, totalA / total)) : 0.5;
  return (
    <View style={styles.splitBar}>
      {/* Send/receive keep the app's one fixed semantic pairing (§3) — red
          for what you give up, green for what you get — matching the dot
          colors on the two side cards below and Trade Hub/Finder's exchange
          rows, instead of a screen-local red/cyan pairing. */}
      <View style={[styles.splitFill, { flex: shareA, backgroundColor: colors.danger }]} />
      <View style={[styles.splitFill, { flex: 1 - shareA, backgroundColor: colors.successBright }]} />
    </View>
  );
}

/**
 * One side (You Send / You Receive) of the comparison being built — same
 * Send/Receive card language as Trade Analyzer/Trade Hub/Trade Finder
 * (§30): a colored dot + label header, and each selected player as a
 * PlayerIdentityRow (tap to remove) inside a grouped surface, instead of a
 * screen-local chip style.
 */
function TradeSide({
  label,
  dotColor,
  players,
  total,
  active,
  onPressHeader,
  onRemove,
}: {
  label: string;
  dotColor: string;
  players: RankedPlayer[];
  total: number;
  active: boolean;
  onPressHeader: () => void;
  onRemove: (playerId: string) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.side, active && styles.sideActive]}>
      <TouchableOpacity style={styles.sideHeader} onPress={onPressHeader} activeOpacity={0.7}>
        <View style={styles.sideLabelRow}>
          <View style={[styles.sideDot, { backgroundColor: dotColor }]} />
          <AppText style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</AppText>
        </View>
        <AppText style={styles.sideTotal}>{Math.round(total)}</AppText>
      </TouchableOpacity>
      {players.length > 0 ? (
        <View style={styles.sideAssetSurface}>
          {players.map((player, index) => (
            <PlayerIdentityRow
              key={player.player_id}
              playerId={player.player_id}
              name={player.name}
              position={player.position}
              team={player.team}
              tier={player.tier}
              onPress={() => onRemove(player.player_id)}
              showDivider={index < players.length - 1}
            />
          ))}
        </View>
      ) : (
        <TouchableOpacity onPress={onPressHeader} activeOpacity={0.7}>
          <AppText style={styles.sideEmpty}>Tap to add</AppText>
        </TouchableOpacity>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
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
  // Same drop-target treatment as Trade Analyzer's side panel: a visible
  // 2pt edge even when inactive (a `surface` fill alone reads too close to
  // `background`), cyan only once this side is the active add target.
  side: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    minHeight: 96,
  },
  sideActive: { borderColor: colors.accent },
  sideHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
  sideLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sideDot: { width: 7, height: 7, borderRadius: 3.5 },
  sideLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  sideLabelActive: { color: colors.accent },
  sideTotal: { fontSize: 20, fontWeight: '700', color: colors.textPrimary },
  sideEmpty: { fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' },
  // Nested inside `side` (a `surface` panel): step *up* the ramp rather than
  // down, so the asset group reads as a raised token instead of a hole
  // punched in the panel at near-identical luminance — same treatment Trade
  // Analyzer/Trade Hub/Trade Finder give their own exchange-side surfaces.
  sideAssetSurface: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
  },
  deltaLabel: {
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  splitBar: {
    flexDirection: 'row',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  splitFill: { height: '100%' },
  positionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff', fontWeight: '700' },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  resultsList: { paddingBottom: spacing.xl },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center' },
  });
}

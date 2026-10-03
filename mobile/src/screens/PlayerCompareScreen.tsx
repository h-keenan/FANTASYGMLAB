import React, { useEffect, useMemo, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnalyticsSection from '../components/AnalyticsSection';
import BrandedSpinner from '../components/BrandedSpinner';
import CircularProgressRing from '../components/CircularProgressRing';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PositionBadge from '../components/PositionBadge';
import { api, type RankedPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { injuryTone } from '../lib/injuryDisplay';
import { percentileColor } from '../lib/percentile';
import {
  buildModelRows,
  buildNarrativePair,
  buildStatusRows,
  buildTrendRows,
  buildValueRows,
  LOWER_IS_BETTER,
  type CompareRow,
  type CompareSide,
  type CompareTextRow,
} from '../lib/playerCompare';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'PlayerCompare'>;

function CompareRowView({ row, isLast }: { row: CompareRow; isLast: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const lowerIsBetter = LOWER_IS_BETTER.has(row.label);
  const hasBoth = row.a !== null && row.b !== null;
  const aWins = hasBoth && row.a !== row.b && (lowerIsBetter ? row.a! < row.b! : row.a! > row.b!);
  const bWins = hasBoth && row.a !== row.b && (lowerIsBetter ? row.b! < row.a! : row.b! > row.a!);
  const display = (value: number | null) => (value === null ? '—' : row.format ? row.format(value) : String(value));
  return (
    <View style={[styles.row, !isLast && styles.rowDivider]}>
      <View style={styles.rowValueColumn}>
        <View style={[styles.rowValuePill, aWins && styles.rowValuePillWin]}>
          <AppText style={[styles.rowValue, aWins && styles.rowValueWin]}>{display(row.a)}</AppText>
        </View>
      </View>
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      <View style={styles.rowValueColumn}>
        <View style={[styles.rowValuePill, bWins && styles.rowValuePillWin]}>
          <AppText style={[styles.rowValue, bWins && styles.rowValueWin]}>{display(row.b)}</AppText>
        </View>
      </View>
    </View>
  );
}

/** Color hint for a text row's value — only Injury Status has a shared,
 * already-defined tone convention (see ../lib/injuryDisplay, the same P0
 * fix Player Detail's Snapshot card uses); every other text row (Status,
 * Role Trend) renders as plain neutral text rather than reinventing a
 * second status-coloring scheme local to this screen. */
function textRowColor(label: string, value: string | null, colors: ThemeColors): string {
  if (label === 'Injury Status') {
    const tone = injuryTone(value);
    if (tone === 'success') return colors.success;
    if (tone === 'danger') return colors.danger;
  }
  return colors.textPrimary;
}

/** Same row shape as CompareRowView but for a CATEGORICAL field (Status,
 * Injury Status, Role Trend direction) — no numeric "winner" pill, since
 * there's no real number to compare, just both sides' real text values
 * placed side by side. */
function CompareTextRowView({ row, isLast }: { row: CompareTextRow; isLast: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const display = (value: string | null) => value || '—';
  return (
    <View style={[styles.row, !isLast && styles.rowDivider]}>
      <View style={styles.rowValueColumn}>
        <AppText style={[styles.rowValueText, { color: textRowColor(row.label, row.a, colors) }]} numberOfLines={2}>
          {display(row.a)}
        </AppText>
      </View>
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      <View style={styles.rowValueColumn}>
        <AppText style={[styles.rowValueText, { color: textRowColor(row.label, row.b, colors) }]} numberOfLines={2}>
          {display(row.b)}
        </AppText>
      </View>
    </View>
  );
}

// Compact identity header for one side of the head-to-head — same portrait +
// "N OVR" ring language PlayerHero uses on Player Detail (§22-23), just sized
// down to sit two-up on one screen instead of PlayerHero's full-width layout.
// Reuses CircularProgressRing/percentileColor directly rather than inventing
// a second ring style for this screen.
function IdentityHeader({ side }: { side: CompareSide }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rating = side.overallRating;
  return (
    <View style={styles.identity}>
      <PlayerAvatar playerId={side.player.player_id} size={56} tier={side.player.tier} />
      {rating !== null ? (
        <CircularProgressRing
          percent={rating}
          size={44}
          strokeWidth={5}
          valueLabel={String(rating)}
          valueFontScale={0.34}
          color={percentileColor(rating, colors)}
          label="OVR"
        />
      ) : null}
      <AppText style={styles.identityName} numberOfLines={2}>
        {side.player.name ?? 'Unknown'}
      </AppText>
      <View style={styles.identityMetaRow}>
        <PositionBadge position={side.player.position} />
        {side.player.team ? (
          <AppText style={styles.identityMeta} numberOfLines={1}>
            {side.player.team}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

/** decision_fit_narrative (QuickViewModel) is a full real sentence — the
 * same "why" copy PlayerDetailScreen's ModelSection renders above its
 * subscore grid — not a number, so it can never be a CompareRow/
 * CompareTextRow. Rendered as two labeled text blocks stacked instead of a
 * row, since two full sentences side-by-side in the narrow two-column row
 * layout would truncate illegibly. Caller only renders this when at least
 * one side actually has a sentence (see buildNarrativePair). */
function NarrativeCompareBlock({
  sideA,
  sideB,
  narrative,
}: {
  sideA: CompareSide;
  sideB: CompareSide;
  narrative: { a: string | null; b: string | null };
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.narrativeGroup}>
      {narrative.a ? (
        <View style={styles.narrativeBlock}>
          <AppText style={styles.narrativeName} numberOfLines={1}>
            {sideA.player.name ?? 'Player A'}
          </AppText>
          <AppText style={styles.narrativeText}>{narrative.a}</AppText>
        </View>
      ) : null}
      {narrative.b ? (
        <View style={styles.narrativeBlock}>
          <AppText style={styles.narrativeName} numberOfLines={1}>
            {sideB.player.name ?? 'Player B'}
          </AppText>
          <AppText style={styles.narrativeText}>{narrative.b}</AppText>
        </View>
      ) : null}
    </View>
  );
}

export default function PlayerCompareScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const { showExplanations } = useDensity();
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
        <View style={styles.discoveryCard}>
          <PlayerIdentityRow
            playerId={player.player_id}
            name={player.name}
            position={player.position}
            team={player.team}
            tier={player.tier}
            contextLine="Choose an opponent below"
          />
          <TextInput
            style={styles.searchInput}
            placeholder="Search for a player to compare"
            value={search}
            onChangeText={setSearch}
            autoCapitalize="none"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        {candidates === null ? (
          <BrandedSpinner style={styles.center} />
        ) : (
          <View style={styles.candidateListCard}>
            <FlatList
              data={filteredCandidates}
              keyExtractor={(item) => item.player_id}
              contentContainerStyle={{ paddingBottom: orbClearance }}
              ListEmptyComponent={
                <EmptyState icon="search-outline" title="No players match" subtitle="Try a different search term." />
              }
              renderItem={({ item, index }) => (
                <PlayerIdentityRow
                  playerId={item.player_id}
                  name={item.name}
                  position={item.position}
                  team={item.team}
                  tier={item.tier}
                  trailingValue={item.score != null ? String(Math.round(item.score)) : null}
                  onPress={() => setPlayerB(item)}
                  showDivider={index !== filteredCandidates.length - 1}
                  style={styles.candidateRow}
                />
              )}
            />
          </View>
        )}
      </View>
    );
  }

  const valueRows = sides ? buildValueRows(sides[0], sides[1]) : [];
  const modelRows = sides ? buildModelRows(sides[0], sides[1]) : [];
  const hasModelRows = modelRows.some((row) => row.a !== null || row.b !== null);
  const trendRows = sides ? buildTrendRows(sides[0], sides[1]) : [];
  const hasTrendRows = trendRows.some((row) => row.a !== null || row.b !== null);
  const statusRows = sides ? buildStatusRows(sides[0], sides[1]) : [];
  const hasStatusRows = statusRows.some((row) => Boolean(row.a) || Boolean(row.b));
  const narrative = sides ? buildNarrativePair(sides[0], sides[1]) : null;

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
        <ScrollView contentContainerStyle={[styles.scrollContent, { paddingBottom: orbClearance }]}>
          <View style={styles.identityRow}>
            <IdentityHeader side={sides[0]} />
            <AppText style={styles.vsLabel}>VS</AppText>
            <IdentityHeader side={sides[1]} />
          </View>
          <AnalyticsSection title="Value & Rank" icon="flash-outline">
            {valueRows.map((row, index) => (
              <CompareRowView key={row.label} row={row} isLast={index === valueRows.length - 1} />
            ))}
          </AnalyticsSection>
          {hasModelRows ? (
            <AnalyticsSection title="Model Breakdown" icon="analytics-outline">
              {modelRows.map((row, index) => (
                <CompareRowView key={row.label} row={row} isLast={index === modelRows.length - 1} />
              ))}
            </AnalyticsSection>
          ) : null}
          {hasStatusRows || hasTrendRows ? (
            <AnalyticsSection title="Trends & Status" icon="trending-up-outline">
              {statusRows.map((row, index) => (
                <CompareTextRowView
                  key={row.label}
                  row={row}
                  isLast={index === statusRows.length - 1 && !hasTrendRows}
                />
              ))}
              {hasTrendRows
                ? trendRows.map((row, index) => (
                    <CompareRowView key={row.label} row={row} isLast={index === trendRows.length - 1} />
                  ))
                : null}
            </AnalyticsSection>
          ) : null}
          {narrative && showExplanations ? (
            <AnalyticsSection title="Decision Fit" icon="chatbubble-ellipses-outline">
              <NarrativeCompareBlock sideA={sides[0]} sideB={sides[1]} narrative={narrative} />
            </AnalyticsSection>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  discoveryCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.background,
    color: colors.textPrimary,
  },
  candidateListCard: {
    flex: 1,
    marginHorizontal: spacing.lg,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  candidateRow: { paddingHorizontal: spacing.md },
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
  scrollContent: { paddingHorizontal: spacing.lg },
  identityRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: spacing.sm },
  identity: { flex: 1, alignItems: 'center', gap: spacing.xs },
  identityName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  identityMeta: { fontSize: 11, color: colors.textSecondary },
  vsLabel: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, marginTop: spacing.xl },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: spacing.sm },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowLabel: {
    flex: 1.1,
    fontSize: 10.5,
    fontWeight: '700',
    color: colors.textSecondary,
    textAlign: 'center',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  rowValueColumn: { flex: 1, alignItems: 'center' },
  rowValuePill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  rowValuePillWin: { backgroundColor: `${colors.successBright}1F`, borderColor: colors.successBright },
  rowValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  rowValueWin: { color: colors.successBright, fontWeight: '800' },
  // Text-row value (Status/Injury Status/Role Trend) — smaller than the
  // numeric rowValue since these are often full words ("Questionable",
  // "Injured Reserve") rather than a compact number, and never gets the
  // win-pill treatment CompareRowView's numeric values get.
  rowValueText: { fontSize: 13, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  narrativeGroup: { gap: spacing.md },
  narrativeBlock: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.sm,
    padding: spacing.md,
    gap: 4,
  },
  narrativeName: { fontSize: 11, fontWeight: '700', color: colors.accent, textTransform: 'uppercase', letterSpacing: 0.3 },
  narrativeText: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  });
}

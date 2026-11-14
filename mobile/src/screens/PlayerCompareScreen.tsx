import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import PressableScale from '../components/PressableScale';
import AppText from '../components/AppText';
import PlayerName from '../components/PlayerName';
import GlassCard from '../components/GlassCard';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnalyticsSection from '../components/AnalyticsSection';
import ValueStat from '../components/ValueStat';
import BrandedSpinner from '../components/BrandedSpinner';
import OvrGauge from '../components/OvrGauge';
import CompareSharePreviewModal from '../components/CompareSharePreviewModal';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import TradePickerSheet from '../components/TradePickerSheet';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import PositionBadge from '../components/PositionBadge';
import ValuesCredit from '../components/ValuesCredit';
import { api, type RankedPlayer, type ScheduleWeek, type WeeklyStatPoint } from '../lib/api';
import { mergeSearchMatches, useLeaguePlayerSearch } from '../lib/leaguePlayerSearch';
import { readRecentOpponents, rememberOpponent } from '../lib/compareRecents';
import {
  NO_EXTRAS,
  buildHeadlineRows,
  buildHeadlineTextRows,
  headlineWinner,
  nextProjection,
  ppgFromWeeks,
  scheduleOutlook,
  suggestedOpponents,
  type CompareExtras,
  type HeadlineRow,
  type HeadlineTextRow,
} from '../lib/compareHeadToHead';
import { pushRecent } from '../lib/compareHeadToHead';
import { playerToSheetItem } from '../lib/tradeSheetItems';
import { useOrbClearance } from '../lib/orbLayout';
import { injuryTone } from '../lib/injuryDisplay';
import {
  buildModelRows,
  buildNarrativePair,
  buildStatusRows,
  buildValueRows,
  compareRowWinner,
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
  const winner = compareRowWinner(row);
  const aWins = winner === 'a';
  const bWins = winner === 'b';
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
    if (tone === 'warning') return colors.warning;
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

/** One headline row: the better side is green with a check, the other side is simply quieter gray. */
function HeadlineRowView({ row, isLast }: { row: HeadlineRow; isLast: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const winner = headlineWinner(row);
  const display = (value: number | null) => (value === null ? '—' : row.format(value));
  const side = (value: number | null, wins: boolean, quiet: boolean) => (
    <View style={styles.rowValueColumn}>
      <View style={[styles.rowValuePill, wins && styles.rowValuePillWin]}>
        <AppText style={[styles.rowValue, wins && styles.rowValueWin, quiet && { color: colors.textTertiary }]} accessibilityLabel={wins ? `Better: ${display(value)}` : undefined}>
          {wins ? '\u2713 ' : ''}
          {display(value)}
        </AppText>
      </View>
    </View>
  );
  return (
    <View style={[styles.row, !isLast && styles.rowDivider]}>
      {side(row.a, winner === 'a', winner === 'b')}
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      {side(row.b, winner === 'b', winner === 'a')}
    </View>
  );
}

function HeadlineTextRowView({ row, isLast }: { row: HeadlineTextRow; isLast: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const side = (value: string | null, wins: boolean, quiet: boolean) => (
    <View style={styles.rowValueColumn}>
      <View style={[styles.rowValuePill, wins && styles.rowValuePillWin]}>
        <AppText style={[styles.rowValueText, wins && { color: colors.successBright }, quiet && { color: colors.textTertiary }]} numberOfLines={2}>
          {value || '—'}
        </AppText>
      </View>
    </View>
  );
  return (
    <View style={[styles.row, !isLast && styles.rowDivider]}>
      {side(row.a, row.winner === 'a', row.winner === 'b')}
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      {side(row.b, row.winner === 'b', row.winner === 'a')}
    </View>
  );
}

/**
 * One of the two big slots: photo, value ring, name, position and team, and
 * value. The whole slot is one tap target that opens the picker; the small
 * info button opens the player card. An empty slot invites a choice.
 */
function CompareSlot({ label, player, onChoose, onInfo, testID }: { label: string; player: RankedPlayer | null; onChoose: () => void; onInfo?: () => void; testID: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.slot, !player && styles.slotEmpty]} testID={testID}>
      <Pressable
        style={styles.slotMain}
        onPress={onChoose}
        accessibilityRole="button"
        accessibilityLabel={player ? `${label}: ${player.name}. Change player` : `${label}: choose a player`}
      >
        {player ? (
          <>
            <View>
              <PlayerAvatar playerId={player.player_id} size={72} tier={player.tier} />
              {player.overall_rating != null ? (
                <View style={styles.slotGauge}>
                  <OvrGauge rating={player.overall_rating} size="sm" />
                </View>
              ) : null}
            </View>
            <AppText style={styles.slotName} numberOfLines={2}>
              {player.name ?? 'Unknown'}
            </AppText>
            <View style={styles.identityMetaRow}>
              <PositionBadge position={player.position} />
              {player.team ? <AppText style={styles.identityMeta}>{player.team}</AppText> : null}
            </View>
            <ValueStat value={player.score != null ? Math.round(player.score) : null} align="center" />
            <AppText style={styles.slotChange}>Change</AppText>
          </>
        ) : (
          <>
            <View style={styles.slotPlus}>
              <AppText style={styles.slotPlusText}>+</AppText>
            </View>
            <AppText style={styles.slotName}>Choose a player</AppText>
            <AppText style={styles.identityMeta}>Same position to start</AppText>
          </>
        )}
      </Pressable>
      {player && onInfo ? (
        <Pressable style={styles.slotInfo} onPress={onInfo} accessibilityRole="button" accessibilityLabel={`${player.name} player card`}>
          <Ionicons name="information-circle-outline" size={22} color={colors.textTertiary} />
        </Pressable>
      ) : null}
    </View>
  );
}

/** One-tap opponent chips: suggested (same position, nearby value) and recent. */
function OpponentChips({ label, players, onPick }: { label: string; players: RankedPlayer[]; onPick: (player: RankedPlayer) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (players.length === 0) return null;
  return (
    <View style={styles.chipSection} accessibilityLabel={label}>
      <AppText style={styles.chipSectionTitle}>{label.toUpperCase()}</AppText>
      <View style={styles.chipWrap}>
        {players.map((p) => (
          <Pressable key={p.player_id} style={styles.oppChip} onPress={() => onPick(p)} accessibilityRole="button" accessibilityLabel={`Compare with ${p.name}`}>
            <PlayerAvatar playerId={p.player_id} size={32} tier={p.tier} />
            <View>
              <PlayerName name={p.name} style={styles.oppName} />
              <AppText style={styles.oppMeta}>
                {p.position} · {p.score != null ? Math.round(p.score).toLocaleString() : '—'}
              </AppText>
            </View>
          </Pressable>
        ))}
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
          <PlayerName name={sideA.player.name ?? 'Player A'} style={styles.narrativeName} />
          <AppText style={styles.narrativeText}>{narrative.a}</AppText>
        </View>
      ) : null}
      {narrative.b ? (
        <View style={styles.narrativeBlock}>
          <PlayerName name={sideB.player.name ?? 'Player B'} style={styles.narrativeName} />
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
  const { player: routePlayer, leagueId, leagueName } = route.params;
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const [playerA, setPlayerA] = useState<RankedPlayer>(routePlayer);
  const [playerB, setPlayerB] = useState<RankedPlayer | null>(null);
  const [picking, setPicking] = useState<'a' | 'b' | null>(null);
  const [pickSearch, setPickSearch] = useState('');
  const [moreOpen, setMoreOpen] = useState(false);
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<RankedPlayer[]>([]);
  const [sides, setSides] = useState<[CompareSide, CompareSide] | null>(null);
  const [weeks, setWeeks] = useState<[WeeklyStatPoint[], WeeklyStatPoint[]] | null>(null);
  const [schedules, setSchedules] = useState<[ScheduleWeek[], ScheduleWeek[]] | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

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
  }, [navigation, leagueId, leagueName, styles]);

  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueRankings(leagueId, { limit: 300 })
      .then((result) => {
        if (!cancelled) setCandidates(result.players);
      })
      .catch(() => {
        if (!cancelled) setCandidates([]);
      });
    readRecentOpponents(leagueId).then((ids) => {
      if (!cancelled) setRecentIds(ids);
    });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!playerB) {
      setSides(null);
      setWeeks(null);
      setSchedules(null);
      return;
    }
    let cancelled = false;
    setLoadingCompare(true);
    Promise.all([api.getPlayerQuickView(playerA.player_id), api.getPlayerQuickView(playerB.player_id)])
      .then(([a, b]) => {
        if (cancelled) return;
        setSides([
          { player: playerA, overallRating: a.stats?.overall_rating ?? null, model: a.model },
          { player: playerB, overallRating: b.stats?.overall_rating ?? null, model: b.model },
        ]);
      })
      .catch(() => {
        if (!cancelled) setSides(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingCompare(false);
      });
    // PPG and the schedule are extras: a failure just leaves their rows blank.
    Promise.all([api.getPlayerWeeklyStats(playerA.player_id), api.getPlayerWeeklyStats(playerB.player_id)])
      .then(([a, b]) => !cancelled && setWeeks([a.weeks, b.weeks]))
      .catch(() => !cancelled && setWeeks(null));
    Promise.all([api.getPlayerSchedule(playerA.player_id), api.getPlayerSchedule(playerB.player_id)])
      .then(([a, b]) => !cancelled && setSchedules([a.weeks ?? [], b.weeks ?? []]))
      .catch(() => !cancelled && setSchedules(null));
    return () => {
      cancelled = true;
    };
  }, [playerA, playerB]);

  // Typed searches also ask the server, so players below the loaded rankings window are found.
  const searchMatches = useLeaguePlayerSearch(leagueId, 'Dynasty', picking ? pickSearch : '');
  const searchPool = useMemo(() => mergeSearchMatches(candidates, searchMatches), [candidates, searchMatches]);
  const sheetItems = useMemo(() => {
    if (!picking) return [];
    const skip = picking === 'a' ? playerB?.player_id : playerA.player_id;
    return searchPool.filter((p) => p.player_id !== skip).map(playerToSheetItem);
  }, [picking, searchPool, playerA.player_id, playerB]);
  // Opens pre-filtered to the position of the player being compared against; one tap on Clear shows everyone.
  const sheetPosition = (picking === 'b' ? playerA.position : picking === 'a' ? (playerB?.position ?? playerA.position) : null) ?? null;

  const suggested = useMemo(() => suggestedOpponents(candidates, playerA, recentIds, 4), [candidates, playerA, recentIds]);
  const recent = useMemo(
    () => recentIds.map((id) => candidates.find((p) => p.player_id === id)).filter((p): p is RankedPlayer => Boolean(p) && p!.player_id !== playerA.player_id).slice(0, 4),
    [recentIds, candidates, playerA.player_id],
  );

  const choose = (chosen: RankedPlayer) => {
    if (picking === 'a') setPlayerA(chosen);
    else setPlayerB(chosen);
    setRecentIds((prev) => pushRecent(prev, chosen.player_id));
    void rememberOpponent(leagueId, chosen.player_id);
    setPicking(null);
  };

  const extrasFor = (index: 0 | 1): CompareExtras =>
    playerB
      ? {
          ppg: weeks ? ppgFromWeeks(weeks[index]) : null,
          projection: schedules ? nextProjection(schedules[index]) : null,
          schedule: schedules ? scheduleOutlook(schedules[index]) : null,
        }
      : NO_EXTRAS;
  const extrasA = extrasFor(0);
  const extrasB = extrasFor(1);
  const headlineRows = playerB ? buildHeadlineRows(playerA, playerB, extrasA, extrasB) : [];
  const headlineTextRows = sides ? buildHeadlineTextRows(sides[0].model, sides[1].model, extrasA, extrasB) : [];
  const valueRows = sides ? buildValueRows(sides[0], sides[1]) : [];
  const modelRows = sides ? buildModelRows(sides[0], sides[1]) : [];
  const hasModelRows = modelRows.some((row) => row.a !== null || row.b !== null);
  const statusRows = sides ? buildStatusRows(sides[0], sides[1]) : [];
  const hasStatusRows = statusRows.some((row) => Boolean(row.a) || Boolean(row.b));
  const narrative = sides ? buildNarrativePair(sides[0], sides[1]) : null;
  const hasMore = hasModelRows || hasStatusRows || Boolean(narrative && showExplanations);

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.scrollContent, { paddingBottom: orbClearance }]} keyboardShouldPersistTaps="handled">
        <View style={styles.slotsRow}>
          <CompareSlot
            testID="compare-slot-a"
            label="Player A"
            player={playerA}
            onChoose={() => {
              setPickSearch('');
              setPicking('a');
            }}
            onInfo={() => openQuickView(playerA, { leagueId, leagueName, sourceLabel: 'Player Compare' })}
          />
          <AppText style={styles.vsLabel}>VS</AppText>
          <CompareSlot
            testID="compare-slot-b"
            label="Player B"
            player={playerB}
            onChoose={() => {
              setPickSearch('');
              setPicking('b');
            }}
            onInfo={playerB ? () => openQuickView(playerB, { leagueId, leagueName, sourceLabel: 'Player Compare' }) : undefined}
          />
        </View>

        {!playerB ? (
          <>
            <OpponentChips label="Suggested" players={suggested} onPick={(p) => choose(p)} />
            <OpponentChips label="Recent" players={recent} onPick={(p) => choose(p)} />
          </>
        ) : (
          <>
            {sides ? (
              <View style={styles.topActionsRow}>
                <PressableScale style={styles.compareShareButton} onPress={() => setShareOpen(true)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Share this comparison">
                  <Ionicons name="share-outline" size={18} color={colors.textSecondary} />
                  <AppText style={styles.changeButtonText}>Share</AppText>
                </PressableScale>
              </View>
            ) : null}
            {loadingCompare && !sides ? <BrandedSpinner style={styles.center} /> : null}
            <GlassCard style={styles.gridCard}>
              <View style={styles.row}>
                <PlayerName name={playerA.name} style={styles.gridName} />
                <View style={styles.rowLabelSpacer} />
                <PlayerName name={playerB.name} style={styles.gridName} />
              </View>
              {headlineRows.map((row, index) => (
                <HeadlineRowView key={row.label} row={row} isLast={index === headlineRows.length - 1 && headlineTextRows.length === 0} />
              ))}
              {headlineTextRows.map((row, index) => (
                <HeadlineTextRowView key={row.label} row={row} isLast={index === headlineTextRows.length - 1} />
              ))}
            </GlassCard>
            <AppText style={styles.legend}>Green marks the better side of each row.</AppText>

            {hasMore && sides ? (
              <>
                <Pressable style={styles.moreButton} onPress={() => setMoreOpen((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: moreOpen }} accessibilityLabel="More stats">
                  <AppText style={styles.moreText}>More stats</AppText>
                  <Ionicons name={moreOpen ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
                </Pressable>
                {moreOpen ? (
                  <>
                    {hasModelRows ? (
                      <AnalyticsSection title="Model Breakdown" icon="analytics-outline">
                        {modelRows.map((row, index) => (
                          <CompareRowView key={row.label} row={row} isLast={index === modelRows.length - 1} />
                        ))}
                      </AnalyticsSection>
                    ) : null}
                    {hasStatusRows ? (
                      <AnalyticsSection title="Status" icon="trending-up-outline">
                        {statusRows.map((row, index) => (
                          <CompareTextRowView key={row.label} row={row} isLast={index === statusRows.length - 1} />
                        ))}
                      </AnalyticsSection>
                    ) : null}
                    {narrative && showExplanations ? (
                      <AnalyticsSection title="Decision Fit" icon="chatbubble-ellipses-outline">
                        <NarrativeCompareBlock sideA={sides[0]} sideB={sides[1]} narrative={narrative} />
                      </AnalyticsSection>
                    ) : null}
                  </>
                ) : null}
              </>
            ) : null}
            <OpponentChips label="Try another" players={suggested} onPick={(p) => choose(p)} />
          </>
        )}
        <ValuesCredit />
      </ScrollView>

      {picking ? (
        <TradePickerSheet
          key={picking}
          mode="single"
          title={picking === 'a' ? 'Choose Player A' : 'Choose a player to compare'}
          subtitle={sheetPosition ? `${sheetPosition} shown first. Clear the filter to see everyone.` : undefined}
          tone="neutral"
          items={sheetItems}
          initialSelected={[]}
          initialFilters={{ positions: sheetPosition ? [sheetPosition.toUpperCase()] : [], conditions: [] }}
          onApply={(keys) => {
            const picked = sheetItems.find((i) => i.key === keys[0]);
            if (picked) choose(picked.ref as RankedPlayer);
          }}
          onClose={() => setPicking(null)}
          onSearch={setPickSearch}
          hideOnInfo
          onInfo={(item, restore) => openQuickView(item.ref as RankedPlayer, { leagueId, leagueName, sourceLabel: 'Player Compare', onClosed: restore })}
        />
      ) : null}

      {sides ? (
        <CompareSharePreviewModal
          visible={shareOpen}
          onClose={() => setShareOpen(false)}
          sideA={{
            playerId: sides[0].player.player_id,
            name: sides[0].player.name ?? 'Unknown',
            position: sides[0].player.position,
            team: sides[0].player.team,
            tier: sides[0].player.tier,
            overallRating: sides[0].overallRating,
          }}
          sideB={{
            playerId: sides[1].player.player_id,
            name: sides[1].player.name ?? 'Unknown',
            position: sides[1].player.position,
            team: sides[1].player.team,
            tier: sides[1].player.tier,
            overallRating: sides[1].overallRating,
          }}
          rows={valueRows}
        />
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  slotsRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md, marginBottom: spacing.md },
  slot: { flex: 1, minWidth: 0, borderRadius: radii.md, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glass },
  slotEmpty: { borderStyle: 'dashed', borderColor: colors.borderStrong },
  slotMain: { minHeight: 200, alignItems: 'center', justifyContent: 'center', gap: spacing.xs, padding: spacing.md },
  slotGauge: { position: 'absolute', right: -14, bottom: -4 },
  slotName: { fontSize: 16, fontWeight: '800', color: colors.textPrimary, textAlign: 'center' },
  slotChange: { fontSize: 13, fontWeight: '800', color: colors.accent },
  slotInfo: { position: 'absolute', right: 0, top: 0, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  slotPlus: { width: 72, height: 72, borderRadius: 36, borderWidth: 2, borderStyle: 'dashed', borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
  slotPlusText: { fontSize: 32, color: colors.accent, lineHeight: 36 },
  chipSection: { gap: spacing.sm, marginBottom: spacing.md },
  chipSectionTitle: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  oppChip: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: 4, paddingLeft: 4, paddingRight: spacing.md, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glass },
  oppName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  oppMeta: { fontSize: 12, color: colors.textTertiary },
  gridCard: { paddingHorizontal: spacing.md, paddingVertical: spacing.xs },
  gridName: { flex: 1, fontSize: 13, fontWeight: '800', color: colors.textSecondary, textAlign: 'center' },
  rowLabelSpacer: { flex: 1.1 },
  legend: { fontSize: 12.5, color: colors.textTertiary, marginTop: spacing.xs, marginBottom: spacing.md },
  moreButton: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, marginBottom: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glass },
  moreText: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  root: { flex: 1, backgroundColor: 'transparent' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  discoveryCard: { marginHorizontal: spacing.lg, marginBottom: spacing.md, gap: spacing.sm },
  candidateListCard: {
    flex: 1,
    marginHorizontal: spacing.lg,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glass,
    overflow: 'hidden',
  },
  candidateRow: { paddingHorizontal: spacing.md },
  // Wraps the existing "Compare someone else" pill plus the new share
  // trigger — centered as a pair so the pill's own former alignSelf:
  // 'center' positioning is unchanged, just now shared with a sibling.
  topActionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  changeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.accentMuted,
  },
  changeButtonText: { fontSize: 13.5, fontWeight: '600', color: colors.accent },
  compareShareButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.xs, minHeight: 44, paddingHorizontal: spacing.sm },
  scrollContent: { paddingHorizontal: spacing.lg },
  identityRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: spacing.sm },
  identity: { flex: 1, alignItems: 'center', gap: spacing.xs },
  identityName: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  identityMeta: { fontSize: 12.5, color: colors.textSecondary },
  vsLabel: { fontSize: 13.5, fontWeight: '800', color: colors.textTertiary },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: spacing.sm },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowLabel: {
    flex: 1.1,
    fontSize: 12,
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
  rowValue: { fontSize: 17, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  rowValueWin: { color: colors.successBright, fontWeight: '800' },
  // Text-row value (Status/Injury Status/Role Trend) — smaller than the
  // numeric rowValue since these are often full words ("Questionable",
  // "Injured Reserve") rather than a compact number, and never gets the
  // win-pill treatment CompareRowView's numeric values get.
  rowValueText: { fontSize: 14.5, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  narrativeGroup: { gap: spacing.md },
  narrativeBlock: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.sm,
    padding: spacing.md,
    gap: 4,
  },
  narrativeName: { fontSize: 12.5, fontWeight: '700', color: colors.accent, textTransform: 'uppercase', letterSpacing: 0.3 },
  narrativeText: { fontSize: 14.5, color: colors.textSecondary, lineHeight: 20 },
  });
}

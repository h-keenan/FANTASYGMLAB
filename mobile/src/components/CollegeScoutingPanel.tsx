import React, { useCallback, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';

import AppText from './AppText';
import FreshnessLabel from './FreshnessLabel';
import { SkeletonList } from './Skeleton';
import EmptyState from './EmptyState';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import PremiumLock from './PremiumLock';
import FilterDropdownButton from './FilterDropdownButton';
import PageControlRow from './PageControlRow';
import ToneBadge from './ToneBadge';
import { api, type CollegeProspect } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { prospectFit, rankByFit, type ProspectFit, type ScoutingLens } from '../lib/scoutingLens';
import { usePlayerListViewMode } from '../lib/viewModePreference';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import ErrorState from './ErrorState';
import ProspectSheet from './ProspectSheet';
import { draftFromProspect, type ReportDraft, type ReportFlash } from './ProspectReportForm';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { handOffPlayerId } from '../lib/prospectProfile';
import { stubPlayer } from '../lib/playerQuickView';

type FilterKey = 'all' | 'watchlist';
type ScoutView = 'base' | 'league';
type ShowOption = 'All prospects' | 'My watchlist';
type ScoutOption = 'Best available' | 'For my league';
const SHOW_OPTIONS: readonly ShowOption[] = ['All prospects', 'My watchlist'];
const SCOUT_OPTIONS: readonly ScoutOption[] = ['Best available', 'For my league'];

function aggregateLabel(prospect: CollegeProspect): string {
  const { avg_grade: avgGrade, scout_count: scoutCount } = prospect.aggregate;
  if (avgGrade == null || scoutCount === 0) return 'Not yet scouted';
  return `${avgGrade.toFixed(1)} avg · ${scoutCount} ${scoutCount === 1 ? 'scout' : 'scouts'}`;
}

/**
 * One prospect row — a bordered surface with hairline dividers per group
 * (Magna Carta §12), matching GmTargetsScreen's grouped-table treatment
 * rather than a per-row card. Trailing star toggles the personal watchlist
 * without leaving this screen; tapping the row itself opens
 * the prospect sheet (stats, profile, your grade).
 *
 * `grid`: coridian_'s 2-up compact card ask (Discord, 2026-10-09) — the
 * exact same fields (position, name, school/class, aggregate scout grade,
 * this user's own grade, watchlist star) reflowed into a vertical card.
 * This screen has no shared PlayerIdentityRow usage to extend (prospects
 * aren't rostered NFL players — no team/tier/injury/portrait, and
 * school/draft-class/scout-grade/watchlist are all genuinely page-specific
 * fields), so the grid variant lives locally here rather than forcing this
 * data into a generic player-row component.
 */
function ProspectRow({
  prospect,
  isFirst,
  isLast,
  grid = false,
  onPress,
  onToggleWatchlist,
  fit = null,
}: {
  prospect: CollegeProspect;
  isFirst: boolean;
  isLast: boolean;
  grid?: boolean;
  onPress: () => void;
  onToggleWatchlist: () => void;
  /** League-overlay badges; null in the base view. */
  fit?: ProspectFit | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const starLabel = prospect.on_watchlist ? 'Remove from watchlist' : 'Add to watchlist';
  const starIcon = prospect.on_watchlist ? 'star' : 'star-outline';
  const starColor = prospect.on_watchlist ? colors.premium : colors.textSecondary;
  const classLabel = `${prospect.school}${prospect.draft_year ? ` · ${prospect.draft_year}` : ''}`;

  const fitBadges =
    fit && (fit.needsPosition || fit.pickNote) ? (
      <View style={styles.fitRow}>
        {fit.needsPosition ? <ToneBadge label="Fits your need" color={colors.success} size="xs" /> : null}
        {fit.pickNote ? <ToneBadge label={fit.pickNote} color={colors.accent} size="xs" /> : null}
      </View>
    ) : null;

  if (grid) {
    return (
      <PressableScale style={styles.gridCell} onPress={onPress}>
        <View style={styles.gridTopRow}>
          <PositionBadge position={prospect.position} />
          <PressableScale
            style={styles.starButton}
            onPress={onToggleWatchlist}
            hitSlop={8}
            accessibilityLabel={starLabel}
          >
            <Ionicons name={starIcon} size={17} color={starColor} />
          </PressableScale>
        </View>
        <PlayerName name={prospect.name} style={styles.gridName} />
        <AppText style={styles.meta}>
          {classLabel}
        </AppText>
        {fitBadges}
        <View style={styles.gridTrailingFooter}>
          <AppText style={styles.aggregate} numberOfLines={1}>
            {aggregateLabel(prospect)}
          </AppText>
          {prospect.my_report ? (
            <AppText style={styles.myGrade} numberOfLines={1}>
              Your grade: {prospect.my_report.grade}/5
            </AppText>
          ) : null}
        </View>
      </PressableScale>
    );
  }

  return (
    <PressableScale
      style={[styles.row, isFirst && styles.rowFirst, isLast && styles.rowLast, !isLast && styles.rowDivider]}
      onPress={onPress}
    >
      <PositionBadge position={prospect.position} />
      <View style={styles.identity}>
        <PlayerName name={prospect.name} style={styles.name} />
        <AppText style={styles.meta}>
          {classLabel}
        </AppText>
        {fitBadges}
      </View>
      <View style={styles.trailing}>
        <AppText style={styles.aggregate} numberOfLines={1}>
          {aggregateLabel(prospect)}
        </AppText>
        {prospect.my_report ? (
          <AppText style={styles.myGrade}>Your grade: {prospect.my_report.grade}/5</AppText>
        ) : null}
      </View>
      <PressableScale style={styles.starButton} onPress={onToggleWatchlist} hitSlop={8} accessibilityLabel={starLabel}>
        <Ionicons name={starIcon} size={18} color={starColor} />
      </PressableScale>
    </PressableScale>
  );
}

/**
 * The shared college prospect board. Lives in Draft Center's Scouting tab and,
 * with no league selected, renders standalone from CollegeProspectsScreen.
 *
 * Layer 1 (always): the league-independent board. Layer 2 (only when `lens` is
 * given, i.e. a league is selected): a "For my league" view that lists
 * prospects matching one of your flagged need positions or a round you hold
 * first and tags them. No new scoring: it reuses My Team's need groups and
 * your pick slots against each prospect's existing community round projection.
 */
export default function CollegeScoutingPanel({
  lens = null,
  leading = null,
}: {
  lens?: ScoutingLens | null;
  /** The page's view select (Players / Prospects), first in the one control row; none on the standalone route. */
  leading?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [prospects, setProspects] = useState<CollegeProspect[]>([]);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [view, setView] = useState<ScoutView>('base');
  const [locked, setLocked] = useState<{ title: string; body: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { viewMode } = usePlayerListViewMode('college-prospects');
  const { openPlayer } = usePlayerQuickView();
  const [openId, setOpenId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ReportDraft>>({});
  const [flashes, setFlashes] = useState<Record<string, ReportFlash>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const onOpenProspect = (prospect: CollegeProspect) => {
    const nflId = handOffPlayerId(prospect);
    if (nflId) {
      openPlayer(stubPlayer({ player_id: nflId, name: prospect.name, position: prospect.position }), { sourceLabel: 'Drafted prospect' });
      return;
    }
    setDrafts((prev) => ({ ...prev, [prospect.id]: prev[prospect.id] ?? draftFromProspect(prospect) }));
    setOpenId(prospect.id);
  };

  const submitReport = async (prospect: CollegeProspect) => {
    const draft = drafts[prospect.id] ?? draftFromProspect(prospect);
    if (draft.grade == null) return;
    setBusyId(prospect.id);
    try {
      const result = await api.submitScoutingReport(prospect.id, { grade: draft.grade, round_projection: draft.roundProjection, note: draft.note.trim() });
      if (result.ok) {
        setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, my_report: { grade: draft.grade, round_projection: draft.roundProjection, note: draft.note.trim() } } : row)));
        setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: 'success', message: 'Saved: thanks for scouting.' } }));
      } else {
        setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: 'error', message: 'Could not save your grade. Try again in a moment.' } }));
      }
    } catch {
      setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: 'error', message: 'Could not save your grade. Try again in a moment.' } }));
    } finally {
      setBusyId(null);
    }
  };

  const removeReport = async (prospect: CollegeProspect): Promise<boolean> => {
    setBusyId(prospect.id);
    try {
      const result = await api.deleteScoutingReport(prospect.id);
      if (!result.ok) return false;
      setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, my_report: null } : row)));
      setDrafts((prev) => ({ ...prev, [prospect.id]: { grade: null, roundProjection: null, note: '' } }));
      setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: 'success', message: 'Removed your report.' } }));
      return true;
    } catch {
      return false;
    } finally {
      setBusyId(null);
    }
  };

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.getCollegeProspects();
      if (result.is_premium === false) {
        setLocked(result.upsell ?? { title: '', body: '' });
        setProspects([]);
        return;
      }
      setLocked(null);
      setProspects(result.prospects);
    } catch (err) {
      setError(toUserErrorMessage(err, 'Failed to load prospects.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const toggleWatchlist = useCallback(async (prospect: CollegeProspect) => {
    const next = !prospect.on_watchlist;
    const set = (value: boolean) =>
      setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: value } : row)));
    set(next);
    try {
      const result = next
        ? await api.addProspectToWatchlist(prospect.id)
        : await api.removeProspectFromWatchlist(prospect.id);
      if (!result.ok) set(!next);
    } catch {
      set(!next);
    }
  }, []);

  const leagueView = Boolean(lens) && view === 'league';
  const visible = useMemo(() => {
    const scoped = filter === 'watchlist' ? prospects.filter((p) => p.on_watchlist) : prospects;
    return lens && leagueView ? rankByFit(scoped, lens) : scoped;
  }, [prospects, filter, lens, leagueView]);

  const controls = (extra: React.ReactNode = null) => (leading || extra ? <PageControlRow testID="prospects-controls">{leading}{extra}</PageControlRow> : null);

  if (loading) {
    return (
      <View style={styles.panel}>
        {controls()}
        <SkeletonList label="prospects" count={6} />
      </View>
    );
  }

  if (locked) {
    return (
      <View style={styles.panel}>
        {controls()}
      <PremiumLock
        feature="college_scouting"
        title={locked.title || 'Scout the next rookie class'}
        description={
          locked.body ||
          'College Scouting is a Pro feature: the shared prospect board, community grades, your own scouting reports and watchlist. Start your free trial to unlock it.'
        }
      />
      </View>
    );
  }

  const grid = viewMode === 'grid';
  const rows = visible.map((item, index) => (
    <ProspectRow
      key={item.id}
      prospect={item}
      isFirst={index === 0}
      isLast={index === visible.length - 1}
      grid={grid}
      fit={lens && leagueView ? prospectFit(item, lens) : null}
      onPress={() => onOpenProspect(item)}
      onToggleWatchlist={() => void toggleWatchlist(item)}
    />
  ));

  const openProspect = openId ? prospects.find((row) => row.id === openId) ?? null : null;
  return (
    <View style={styles.panel}>
      <FreshnessLabel datasets={['prospects']} />
      {openProspect ? (
        <ProspectSheet
          key={openProspect.id}
          prospect={openProspect}
          draft={drafts[openProspect.id] ?? draftFromProspect(openProspect)}
          flash={flashes[openProspect.id] ?? null}
          busy={busyId === openProspect.id}
          onDraftChange={(next) => setDrafts((prev) => ({ ...prev, [openProspect.id]: next }))}
          onSubmit={() => void submitReport(openProspect)}
          onRemove={() => removeReport(openProspect)}
          onToggleWatchlist={() => void toggleWatchlist(openProspect)}
          onClose={() => setOpenId(null)}
        />
      ) : null}
      {controls(
        <>
          <FilterDropdownButton<ShowOption>
            select
            label="Show"
            options={SHOW_OPTIONS}
            value={filter === 'watchlist' ? 'My watchlist' : 'All prospects'}
            onChange={(next) => setFilter(next === 'My watchlist' ? 'watchlist' : 'all')}
            testID="prospects-show-select"
          />
          {lens ? (
            <FilterDropdownButton<ScoutOption>
              select
              label="Scouting view"
              options={SCOUT_OPTIONS}
              value={leagueView ? 'For my league' : 'Best available'}
              onChange={(next) => setView(next === 'For my league' ? 'league' : 'base')}
              testID="prospects-scouting-select"
            />
          ) : null}
        </>,
      )}
      {leagueView ? (
        <AppText style={styles.lensNote}>Prospects that fit a position you need or a round you hold are listed first and tagged. Same prospects and grades as Best available.</AppText>
      ) : null}
      {error ? <ErrorState compact title="Couldn't load prospects" message={error} onRetry={() => void load()} /> : null}
      {visible.length === 0 ? (
        <EmptyState
          icon={filter === 'watchlist' ? 'star-outline' : 'school-outline'}
          title={filter === 'watchlist' ? 'No prospects followed yet' : 'No prospects yet'}
          subtitle={
            filter === 'watchlist'
              ? 'Tap the star on any prospect to follow them here.'
              : 'Check back soon: the prospect pool is still growing.'
          }
        />
      ) : grid ? (
        <View style={styles.gridWrap}>{rows}</View>
      ) : (
        rows
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    panel: { gap: spacing.sm },
    lensBlock: { gap: spacing.xs },
    lensNote: { fontSize: 12.5, color: colors.textSecondary },
    fitRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: 2 },
    gridWrap: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: spacing.sm },
    center: { alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.xl },
    tabRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: spacing.sm,
    },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      backgroundColor: colors.glass,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
    },
    rowFirst: {
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopLeftRadius: radii.md,
      borderTopRightRadius: radii.md,
    },
    rowLast: {
      borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
      borderBottomLeftRadius: radii.md,
      borderBottomRightRadius: radii.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    identity: { flex: 1, minWidth: 0 },
    name: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12.5, color: colors.textSecondary, marginTop: 1 },
    trailing: { alignItems: 'flex-end', gap: 1 },
    aggregate: { fontSize: 12.5, fontWeight: '600', color: colors.textSecondary },
    myGrade: { fontSize: 12, color: colors.accent, marginTop: 1 },
    starButton: { padding: spacing.xs },
    // Grid (2-up compact card) mode — see ProspectRow's `grid` branch. Same
    // width/space-between approach as the other grid-ified list screens
    // (keeps an unpaired last card from stretching to double width).
        gridCell: {
      width: '48%',
      backgroundColor: colors.glass,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      padding: spacing.sm,
      gap: 2,
    },
    gridTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    gridName: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
    gridTrailingFooter: {
      marginTop: spacing.xs,
      paddingTop: spacing.xs,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
      gap: 1,
    },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
  });
}

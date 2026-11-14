import React, { useEffect, useMemo, useReducer, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import Input from './Input';
import MetricCard from './MetricCard';
import { simAsOfSeason } from '../lib/simAsOf';
import PlayerQuickViewSheet, { Section as PqvSection, type SimPqvSections } from './PlayerQuickViewSheet';
import { SimPlayerHistory } from './SimPlayerHistory';
import SimScoutingSections from './SimScoutingSections';
import WeeklyPointsChart from './WeeklyPointsChart';
import { ReviewGlyphChip } from './SeasonReviewSections';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimDraftRow } from './SimDraftBoard';
import { SimPager, SimToneBadge, createSimStyles, useSimDebounced } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { stubPlayer } from '../lib/playerQuickView';
import { SIM_WINDOW_STEP, simWindow } from '../lib/simLayout';
import { simActualPoints, simAvailabilityLine, simHeroFeed, simProjectionBand, simProjectionIsFlat, simRosLine } from '../lib/simPlayerSheet';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  simStatusOptions,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtPts,
  simFmtValue,
  simHeadshotId,
  simIfStartsHint,
  simPlayerTags,
  simOwnerLabel,
  simOwnerTone,
  simRoleBadge,
  simPageCount,
  simPlayerStatusLabel,
  type SimGamePlayer,
  type SimPlayerDetailResponse,
  type SimPlayerFilter,
  type SimPlayerSort,
  type SimPlayerStatusFilter,
  type SimPosFilter,
} from '../lib/simGame';
import { spacing } from '../theme';

/**
 * Searchable, filterable, sortable list of every player in the game: owner
 * (you / AI team / free agent), projection and value. Used as the draft board
 * (status fixed to "available") and as the weekly Players tab. Server-side
 * paging and filtering (GET /players); a changed filter returns to page 1
 * (simFilterReducer) and a late response for an old filter is ignored.
 */
export function SimPlayerBrowser({
  gameId,
  fixedStatus,
  initial,
  actions,
  onOpen,
  refreshKey = 0,
  onItems,
  emptyTitle = 'No players match',
  week = 0,
  blockEnabled = false,
  positions = SIM_POSITIONS.map((pos) => ({ label: pos as string, value: pos as SimPosFilter })),
}: {
  gameId: string;
  /** Positions this league plays (no K / DEF chips when it has no such slot). */
  /** Filter segments after "All" (simFilterPositionsFor). */
  positions?: { label: string; value: SimPosFilter }[];
  /** Current game week, to flag a bye that is close. */
  week?: number;
  /** The game has a trade block: adds the "On the block" status filter. */
  blockEnabled?: boolean;
  /** Lock the status filter (the draft board is always free agents). */
  fixedStatus?: SimPlayerStatusFilter;
  initial?: Partial<SimPlayerFilter>;
  actions?: (player: SimGamePlayer) => ReactNode;
  onOpen: (player: SimGamePlayer) => void;
  /** Bump to refetch after a pick / add / trade. */
  refreshKey?: number;
  onItems?: (items: SimGamePlayer[]) => void;
  emptyTitle?: string;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [filter, dispatch] = useReducer(simFilterReducer, simDefaultFilter({ status: fixedStatus ?? '', ...initial }));
  const [text, setText] = useState(filter.q);
  const debouncedText = useSimDebounced(text, PLAYER_SEARCH_DEBOUNCE_MS);
  const [items, setItems] = useState<SimGamePlayer[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [attempt, setAttempt] = useState(0);
  // A new page or filter starts at the top window again (the window is keyed to the filter).
  const windowKey = [filter.page, filter.pos, filter.sort, filter.q, filter.status].join('|');
  const [win, setWin] = useState({ key: windowKey, n: SIM_WINDOW_STEP });
  const visible = win.key === windowKey ? win.n : SIM_WINDOW_STEP;
  const rows = simWindow(items, visible);

  useEffect(() => {
    dispatch({ type: 'q', value: debouncedText });
  }, [debouncedText]);

  const query = useMemo(() => simFilterQuery({ ...filter, status: fixedStatus ?? filter.status }), [filter, fixedStatus]);

  useEffect(() => {
    const controller = new AbortController();
    setState((s) => (s === 'error' ? 'loading' : s));
    api
      .getSimGamePlayers(gameId, query, controller.signal)
      .then((body) => {
        if (controller.signal.aborted) return;
        setItems(body.items ?? []);
        setTotal(body.total ?? 0);
        setState('ready');
        onItems?.(body.items ?? []);
      })
      .catch(() => {
        if (!controller.signal.aborted) setState('error');
      });
    return () => controller.abort();
    // onItems is a stable setter from the caller; refetch on refreshKey / retry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, query, refreshKey, attempt]);

  return (
    <View style={common.stack}>
      <Input
        value={text}
        onChangeText={setText}
        placeholder="Search players or NFL teams"
        accessibilityLabel="Search players"
        returnKeyType="search"
        autoCorrect={false}
        autoCapitalize="none"
        clearButtonMode="while-editing"
      />
      <SegmentedTabBar<string>
        scrollable
        options={[{ key: '', label: 'All' }, ...positions.map((p) => ({ key: p.value as string, label: p.label }))]}
        active={filter.pos}
        onChange={(key) => dispatch({ type: 'pos', value: key as SimPosFilter | '' })}
      />
      {!fixedStatus ? (
        <SegmentedTabBar<string>
          scrollable
          options={simStatusOptions(blockEnabled).map((o) => ({ key: o.value as string, label: o.label }))}
          active={filter.status}
          onChange={(key) => dispatch({ type: 'status', value: key as SimPlayerStatusFilter })}
        />
      ) : null}
      <View style={common.tight}>
        <AppText style={common.muted}>Sort by</AppText>
        <SegmentedTabBar<string>
          scrollable
          options={SIM_SORT_OPTIONS.map((o) => ({ key: o.value as string, label: o.label }))}
          active={filter.sort}
          onChange={(key) => dispatch({ type: 'sort', value: key as SimPlayerSort })}
        />
      </View>
      {state === 'loading' && items.length === 0 ? (
        <SkeletonCard rows={6} />
      ) : state === 'error' ? (
        <EmptyState
          icon="cloud-offline-outline"
          title="Players did not load"
          subtitle="Check your connection and try again."
          actionLabel="Try again"
          onPressAction={() => {
            setState('loading');
            setAttempt((n) => n + 1);
          }}
        />
      ) : items.length === 0 ? (
        <EmptyState icon="search-outline" title={emptyTitle} subtitle="Try a different search or filter." />
      ) : (
        <View style={{ opacity: state === 'loading' ? 0.6 : 1 }}>
          <AppText style={common.muted} accessibilityLiveRegion="polite">
            {total} player{total === 1 ? '' : 's'}
          </AppText>
          {rows.shown.map((player) => (
            <SimDraftRow
              key={player.id}
              player={player}
              week={week}
              onOpen={onOpen}
              tags={simPlayerTags(player)}
              actions={actions ? actions(player) : null}
            />
          ))}
          {rows.remaining > 0 ? (
            <Pressable onPress={() => setWin({ key: windowKey, n: visible + SIM_WINDOW_STEP })} accessibilityRole="button" style={{ minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
              <AppText style={{ fontSize: 14, fontWeight: '800', color: colors.accent }}>
                Show {Math.min(SIM_WINDOW_STEP, rows.remaining)} more on this page ({rows.remaining} left)
              </AppText>
            </Pressable>
          ) : null}
        </View>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: 'page', value: page })} />
    </View>
  );
}

/**
 * The game's player detail IS the app's shared Player Quick View: the same
 * sheet (hero tiles, news, stats, trends, bio, model) fed by an adapter that
 * maps the sim player to a quick-view identity (real Sleeper id -> real data
 * from the main API; a generated player has no real data, so the hero tiles
 * take the sim's own value and ranks), plus sim sections rendered with the
 * quick view's own section shell, tiles and weekly chart.
 */
export function SimPlayerSheet({ gameId, player, onClose, actions, startYear }: { gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode; /** game.settings.start_year: drives the as-of cut of real data. */ startYear?: number | null }) {
  const detail = useSimPlayerDetail(gameId, player.id);
  const live = detail.data?.player ?? player;
  const real = simHeadshotId(player);
  const feed = real ? null : simHeroFeed(live);
  const request = {
    player: {
      ...stubPlayer({ player_id: real ?? player.id, name: player.name, position: player.pos, team: player.team ?? null }),
      age: player.age ?? null,
      injury_status: live.status === 'out' ? 'Out' : null,
      // The list rows' Overall also drives the hero's Player score ring, so the number never differs between a row and its quick view.
      overall_rating: live.overall ?? null,
      ...(feed ? { overall_rank: feed.overall_rank, position_rank: feed.position_rank } : {}),
    },
    league: null,
    sourceLabel: 'Fantasy Sim',
  };
  return <PlayerQuickViewSheet request={request} onClose={onClose} remote={Boolean(real)} asOfSeason={simAsOfSeason(startYear)} simSections={simPqvSections(gameId, live, detail, actions)} />;
}

interface SimPlayerDetailState {
  data: SimPlayerDetailResponse | null;
  failed: boolean;
}

function useSimPlayerDetail(gameId: string, playerId: string): SimPlayerDetailState {
  const key = `${gameId}/${playerId}`;
  const [state, setState] = useState<SimPlayerDetailState & { key: string }>({ data: null, failed: false, key: '' });
  useEffect(() => {
    let cancelled = false;
    api
      .getSimGamePlayer(gameId, playerId)
      .then((body) => {
        if (!cancelled) setState({ data: body, failed: false, key });
      })
      .catch(() => {
        if (!cancelled) setState({ data: null, failed: true, key });
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, playerId, key]);
  return state.key === key ? state : { data: null, failed: false };
}

/**
 * The sim-only sections of the player detail, split by tab of the shared Player Quick View: Overview, Outlook, Scouting
 * (generated rookies) and History (derived from the event log), in the quick view's own section shell, tiles and chart.
 */
export function simPqvSections(gameId: string, player: SimGamePlayer, detail: SimPlayerDetailState, actions?: ReactNode): SimPqvSections {
  return {
    overview: <SimOverviewSection player={player} detail={detail} actions={actions} />,
    outlook: <SimOutlookSection player={player} detail={detail} />,
    scouting: detail.data?.scouting ? <SimScoutingSections profile={detail.data.scouting} /> : undefined,
    history: <SimPlayerHistory gameId={gameId} playerId={player.id} />,
  };
}

function SimOverviewSection({ player, detail, actions }: { player: SimGamePlayer; detail: SimPlayerDetailState; actions?: ReactNode }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(), []);
  const body = detail.data;
  const status = simPlayerStatusLabel(player);
  const ros = body?.ros ?? null;
  return (
    <View style={styles.overlay} testID="sim-player-overlay">
      <PqvSection
        title="In this game"
        right={
          <View style={common.wrapRow}>
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {player.owner ? <SimToneBadge label={simOwnerLabel(player.owner)} tone={simOwnerTone(player.owner)} /> : null}
            {simRoleBadge(player) ? <SimToneBadge label={simRoleBadge(player)!.label} tone={simRoleBadge(player)!.tone} /> : null}
          </View>
        }
      >
        <View style={styles.tileGrid}>
          <MetricCard label="This week" value={simFmtPts(player.projection)} note={status ? status.label : `${simFmtPts(player.floor)}-${simFmtPts(player.ceiling)}`} />
          {ros ? <MetricCard label="Rest of season" value={`${simFmtPts(ros.mean)} ppg`} note={`${simFmtPts(ros.floor)}-${simFmtPts(ros.ceiling)}`} /> : null}
          <MetricCard
            label="This season"
            value={simFmtPts(player.season_points ?? 0)}
            note={`${player.games ?? 0} games${player.ppg != null ? ` · ${simFmtPts(player.ppg)} ppg` : ''}`}
          />
          <MetricCard
            label="Overall"
            value={player.overall != null ? String(player.overall) : null}
            note={player.adp != null ? `ADP ${simFmtValue(player.adp)}` : 'No ADP'}
          />
        </View>
        {simIfStartsHint(player) ? <AppText style={common.muted} testID="sim-if-starts">{simIfStartsHint(player)}</AppText> : null}
        {actions ? <View style={common.wrapRow}>{actions}</View> : null}
      </PqvSection>
      {(body?.news ?? []).length > 0 ? (
        <PqvSection title="Game news">
          <View style={common.stack}>
            {body!.news!.map((n, i) => (
              <View key={i} style={common.row}>
                <ReviewGlyphChip glyph="stats" tone="accent" size={22} />
                <AppText style={[common.body, common.grow]}>
                  <AppText style={[common.muted, { color: colors.accent, fontWeight: '700' }]}>Week {n.week} · </AppText>
                  {n.text}
                </AppText>
              </View>
            ))}
          </View>
        </PqvSection>
      ) : null}
    </View>
  );
}

function SimOutlookSection({ player, detail }: { player: SimGamePlayer; detail: SimPlayerDetailState }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(), []);
  const body = detail.data;
  if (detail.failed) return <AppText style={common.small}>The full outlook is unavailable right now.</AppText>;
  if (!body) return <SkeletonCard rows={2} />;
  const ros = body.ros ?? null;
  const flat = simProjectionIsFlat(body);
  const band = simProjectionBand(body);
  const actual = simActualPoints(body);
  const availability = ros ? simAvailabilityLine(ros) : null;
  if (!(actual.length > 0 || band || ros)) return <AppText style={common.small}>No outlook yet.</AppText>;
  return (
    <View style={styles.overlay}>
      <PqvSection title="Week by Week · This sim season">
        {actual.length > 0 || band ? (
          <WeeklyPointsChart weeks={actual.map((a) => ({ week: a.week, fantasy_points_ppr: a.points, snap_share: null }))} projection={band} pointsLabel="pts" />
        ) : null}
        {flat && ros ? (
          <AppText style={common.small} testID="sim-ros-line">
            <AppText style={common.bodyStrong}>{simRosLine(ros)}</AppText>
            {availability ? ` · ${availability}` : ''}
          </AppText>
        ) : availability ? (
          <AppText style={common.small}>{availability}</AppText>
        ) : null}
      </PqvSection>
    </View>
  );
}

function createStyles() {
  return StyleSheet.create({
    overlay: { gap: spacing.md, paddingTop: spacing.sm },
    tileGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  });
}

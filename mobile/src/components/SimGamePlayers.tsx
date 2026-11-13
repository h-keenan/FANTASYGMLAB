import React, { useEffect, useMemo, useReducer, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import Input from './Input';
import Collapsible from './Collapsible';
import PlayerQuickViewSheet from './PlayerQuickViewSheet';
import { ReviewGlyphChip } from './SeasonReviewSections';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPager, SimPlayerLine, SimStat, SimToneBadge, createSimStyles, useSimDebounced } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { stubPlayer } from '../lib/playerQuickView';
import { SIM_WINDOW_STEP, simWindow } from '../lib/simLayout';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  SIM_STATUS_OPTIONS,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtProjection,
  simFmtPts,
  simFmtValue,
  simHeadshotId,
  simOwnerLabel,
  simOwnerTone,
  simPageCount,
  simPlayerStatusLabel,
  type SimGamePlayer,
  type SimPlayerDetailResponse,
  type SimPlayerFilter,
  type SimPlayerSort,
  type SimPlayerStatusFilter,
  type SimPos,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

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
  positions = SIM_POSITIONS,
}: {
  gameId: string;
  /** Positions this league plays (no K / DEF chips when it has no such slot). */
  positions?: SimPos[];
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
  const { width } = useWindowDimensions();
  const showValue = width >= 640;
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
        options={[{ key: '', label: 'All' }, ...positions.map((pos) => ({ key: pos as string, label: pos }))]}
        active={filter.pos}
        onChange={(key) => dispatch({ type: 'pos', value: key as SimPos | '' })}
      />
      {!fixedStatus ? (
        <SegmentedTabBar<string>
          scrollable
          options={SIM_STATUS_OPTIONS.map((o) => ({ key: o.value as string, label: o.label }))}
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
            <SimPlayerLine
              key={player.id}
              player={player}
              onOpen={onOpen}
              extra={
                <>
                  {player.owner ? <SimToneBadge label={simOwnerLabel(player.owner)} tone={simOwnerTone(player.owner)} /> : null}
                  {player.adp != null ? <AppText style={common.muted}>ADP {simFmtValue(player.adp)}</AppText> : null}
                </>
              }
              trailing={
                <>
                  <SimStat label="Proj" value={simFmtPts(player.projection)} />
                  {showValue ? <SimStat label="Value" value={simFmtValue(player.value)} /> : null}
                  {actions ? actions(player) : null}
                </>
              }
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
 * sheet (hero, news, stats, trends, bio, model) fed by an adapter that maps
 * the sim player to a quick-view identity (real Sleeper id -> real data from
 * the main API), plus a sim overlay with what only this game knows. A
 * synthetic player (no real id) renders the same layout with remote={false}.
 */
export function SimPlayerSheet({ gameId, player, onClose, actions }: { gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode }) {
  const real = simHeadshotId(player);
  const request = {
    player: {
      ...stubPlayer({ player_id: real ?? player.id, name: player.name, position: player.pos, team: player.team ?? null }),
      age: player.age ?? null,
      injury_status: player.status === 'out' ? 'Out' : null,
    },
    league: null,
    sourceLabel: 'Fantasy Sim',
  };
  return <PlayerQuickViewSheet request={request} onClose={onClose} remote={Boolean(real)} simOverlay={<SimPlayerOverlay gameId={gameId} player={player} actions={actions} />} />;
}

/** The sim-only sections of the player detail, as phone-friendly collapsibles. */
export function SimPlayerOverlay({ gameId, player, actions }: { gameId: string; player: SimGamePlayer; actions?: ReactNode }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [detail, setDetail] = useState<SimPlayerDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .getSimGamePlayer(gameId, player.id)
      .then((body) => {
        if (!cancelled) setDetail(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, player.id]);

  const live = detail?.player ?? player;
  const status = simPlayerStatusLabel(live);
  const weeks = detail?.weeks ?? [];
  const maxCeiling = Math.max(1, ...weeks.map((w) => w.ceiling));
  const pct = (value: number) => `${Math.max(0, Math.min(100, (value / maxCeiling) * 100))}%` as const;
  const title = (text: string) => <AppText style={styles.foldTitle}>{text}</AppText>;
  return (
    <View style={common.stack} testID="sim-player-overlay">
      <Collapsible
        id="player.sim"
        accent={colors.accent}
        defaultOpen
        title={title('In this game')}
        summary={
          <View style={common.wrapRow}>
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {live.owner ? <SimToneBadge label={simOwnerLabel(live.owner)} tone={simOwnerTone(live.owner)} /> : null}
          </View>
        }
      >
        <View style={styles.statGrid}>
          <View style={styles.statCell}>
            <AppText style={common.muted}>This week</AppText>
            <AppText style={styles.statBig}>{simFmtPts(live.projection)}</AppText>
            <AppText style={common.muted}>
              {simFmtPts(live.floor)}-{simFmtPts(live.ceiling)}
            </AppText>
          </View>
          <View style={styles.statCell}>
            <AppText style={common.muted} accessibilityHint="Model value on the game's 0-100 scale">
              Value
            </AppText>
            <AppText style={styles.statBig}>{simFmtValue(live.value)}</AppText>
            <AppText style={common.muted}>ADP {simFmtValue(live.adp)}</AppText>
          </View>
          <View style={styles.statCell}>
            <AppText style={common.muted}>Season</AppText>
            <AppText style={styles.statBig}>{simFmtPts(live.season_points ?? 0)}</AppText>
            <AppText style={common.muted}>{live.games ?? 0} games</AppText>
          </View>
        </View>
        {actions ? <View style={common.wrapRow}>{actions}</View> : null}
      </Collapsible>
      {failed ? (
        <AppText style={common.small}>The full outlook is unavailable right now.</AppText>
      ) : !detail ? (
        <SkeletonCard rows={2} />
      ) : (
        <>
          {weeks.length > 0 ? (
            <Collapsible id="player.sim.weeks" accent={colors.accent} defaultOpen={false} title={title('Week by week')} summary={<AppText style={common.muted}>{weeks.length} weeks</AppText>}>
              <View style={common.stack} accessibilityLabel="Week-by-week projection">
                {weeks.map((w) => (
                  <View key={w.week} style={styles.weekRow}>
                    <AppText style={styles.weekLabel}>W{w.week}</AppText>
                    {w.bye || w.out ? (
                      <AppText style={[common.small, { color: w.out ? colors.danger : colors.warning }]}>{w.out ? 'Out' : 'Bye'}</AppText>
                    ) : (
                      <>
                        <View
                          style={styles.track}
                          accessible
                          accessibilityRole="image"
                          accessibilityLabel={`Week ${w.week} projection ${simFmtPts(w.projection)}, range ${simFmtPts(w.floor)} to ${simFmtPts(w.ceiling)}`}
                        >
                          <View style={[styles.band, { left: pct(w.floor), width: `${Math.max(2, ((w.ceiling - w.floor) / maxCeiling) * 100)}%` }]} />
                          <View style={[styles.mark, { left: pct(w.projection) }]} />
                        </View>
                        <AppText style={styles.weekValue}>{simFmtProjection(w)}</AppText>
                      </>
                    )}
                  </View>
                ))}
              </View>
            </Collapsible>
          ) : null}
          {(detail.history ?? []).length > 0 ? (
            <Collapsible id="player.sim.results" accent={colors.success} defaultOpen title={title('Results so far')}>
              <View style={common.wrapRow}>
                {detail.history!.map((h) => (
                  <View key={h.week} style={styles.chip}>
                    <AppText style={common.muted}>W{h.week} </AppText>
                    <AppText style={common.bodyStrong}>{simFmtPts(h.points)}</AppText>
                  </View>
                ))}
              </View>
            </Collapsible>
          ) : null}
          {(detail.news ?? []).length > 0 ? (
            <Collapsible id="player.sim.news" accent={colors.warning} defaultOpen title={title('Game news')}>
              <View style={common.stack}>
                {detail.news!.map((n, i) => (
                  <View key={i} style={common.row}>
                    <ReviewGlyphChip glyph="stats" tone="accent" size={22} />
                    <AppText style={[common.body, common.grow]}>
                      <AppText style={[common.muted, { color: colors.accent, fontWeight: '700' }]}>Week {n.week} · </AppText>
                      {n.text}
                    </AppText>
                  </View>
                ))}
              </View>
            </Collapsible>
          ) : null}
        </>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    statGrid: { flexDirection: 'row', gap: spacing.sm },
    statCell: { flex: 1, minWidth: 0 },
    foldTitle: { fontSize: 14, fontWeight: '800', textTransform: 'uppercase', color: colors.textPrimary },
    statBig: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    weekRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    weekLabel: { width: 34, fontSize: 13, fontWeight: '700', color: colors.textTertiary },
    weekValue: { width: 92, textAlign: 'right', fontSize: 13, fontWeight: '600', color: colors.textPrimary },
    track: { flex: 1, height: 10, borderRadius: 5, overflow: 'hidden', backgroundColor: colors.backgroundElevated },
    band: { position: 'absolute', top: 0, bottom: 0, borderRadius: 5, backgroundColor: colors.accentMuted },
    mark: { position: 'absolute', top: 0, bottom: 0, width: 3, backgroundColor: colors.accentStrong },
    chip: {
      flexDirection: 'row',
      alignItems: 'baseline',
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs,
      borderRadius: 12,
      backgroundColor: colors.glass,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.glassBorder,
    },
  });
}

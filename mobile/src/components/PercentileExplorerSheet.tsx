import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PanResponder, StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';

import AppText from './AppText';
import PlayerName from './PlayerName';
import EmptyState from './EmptyState';
import Input from './Input';
import PlayerAvatar from './PlayerAvatar';
import SegmentedTabBar from './SegmentedTabBar';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import Tabs from './Tabs';
import { percentileTabs } from '../lib/sheetTabs';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { trackUse } from '../lib/analytics';
import {
  addPin,
  assignMarkerLanes,
  binIndexAtPercentile,
  bucketPlayers,
  defaultComparison,
  explorerEmptyCopy,
  explorerMetricsFor,
  explorerViewState,
  formatExplorerDelta,
  formatExplorerValue,
  playersNearPercentile,
  poolMedian,
  rosterIdsFromRoster,
  searchExplorerPool,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from '../lib/percentileExplorer';
import { ordinal, percentileColor } from '../lib/percentile';
import { radii, scrim, spacing, type ThemeColors } from '../theme';
import ErrorState from './ErrorState';

const LANE_STEP = 74;
const BAR_AREA = 88;
const AXIS_H = 22;
const MARKER_W = 104;
const LIST_CAP = 30;
const LIST_PREVIEW = 8;

type LoadState = { status: 'loading' | 'error' } | { status: 'ready'; data: PercentileExplorerResponse };

/**
 * Percentile Explorer: bottom sheet behind one stat tile on Player Detail.
 * Same data as web (GET /v1/players/{id}/percentile-explorer?full=true).
 * Explorable: switch metric, scrub or tap the histogram to list a bucket, search
 * any pool player onto the chart, roster marks, and a pinned head-to-head. Every
 * player label is first initial + full last name (lib/formatPlayerName).
 */
export default function PercentileExplorerSheet({
  playerId,
  statKey,
  statLabel,
  leagueId,
  onClose,
  onOpenPlayer,
}: {
  playerId: string;
  statKey: string;
  statLabel: string;
  /** When set, the user's rostered players are marked distinctly. */
  leagueId?: string | null;
  onClose: () => void;
  onOpenPlayer: (player: ExplorerPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [metric, setMetric] = useState({ key: statKey, label: statLabel });
  const [pool, setPool] = useState<'position' | 'all'>('position');
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [retryToken, setRetryToken] = useState(0);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [pins, setPins] = useState<string[]>([]);
  const [swapped, setSwapped] = useState(false);
  const [focusPct, setFocusPct] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [showAllBucket, setShowAllBucket] = useState(false);
  const [rosterIds, setRosterIds] = useState<Set<string>>(() => new Set());
  const [chartWidth, setChartWidth] = useState(0);
  const chartWidthRef = useRef(0);
  const scrubStartX = useRef(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getPercentileExplorer(playerId, metric.key, pool, true)
      .then((data) => {
        if (cancelled) return;
        const known = new Set([...(data.pool_players ?? []), ...(data.nearby ?? [])].map((p) => p.player_id));
        const seeded = (data.nearby ?? []).map((p) => p.player_id);
        // Keep pins that still exist in this pool; top up with nearby players.
        setPins((prev) => {
          const kept = prev.filter((id) => known.has(id) && id !== playerId);
          return kept.length >= 3 ? kept : [...kept, ...seeded.filter((id) => !kept.includes(id))].slice(-7);
        });
        setState({ status: 'ready', data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, metric.key, pool, retryToken]);

  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    api
      .getMyRoster(leagueId)
      .then((res) => {
        if (!cancelled && !res.reason) setRosterIds(rosterIdsFromRoster(res.roster));
      })
      .catch(() => {
        // Best-effort: no roster means no roster marks, never a guess.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const data = state.status === 'ready' ? state.data : null;
  const view = explorerViewState(state.status, data);
  const me = data?.player ?? null;
  const nearby = useMemo(() => data?.nearby ?? [], [data]);
  const poolPlayers = useMemo(() => data?.pool_players ?? (me ? [...nearby, me] : []), [data, me, nearby]);
  const hasFullPool = (data?.pool_players?.length ?? 0) > 0;
  const byId = useMemo(() => new Map(poolPlayers.map((p) => [p.player_id, p])), [poolPlayers]);
  const comparison = useMemo(() => {
    if (!me) return null;
    const picked = pickedId ? byId.get(pickedId) : null;
    return picked && picked.player_id !== me.player_id ? picked : defaultComparison(me, nearby);
  }, [me, nearby, pickedId, byId]);
  const markers = useMemo(() => {
    if (!me) return [];
    const ids = new Set(pins);
    if (comparison) ids.add(comparison.player_id);
    const others = [...ids].map((id) => byId.get(id)).filter((p): p is ExplorerPlayer => !!p && p.player_id !== me.player_id);
    return [...others, me].sort((a, b) => a.percentile - b.percentile);
  }, [me, pins, comparison, byId]);
  // Labels are ~MARKER_W wide; keep neighbours that close on different lanes.
  const minGap = chartWidth > 0 ? Math.max(30, (MARKER_W / chartWidth) * 100) : 30;
  const lanes = useMemo(() => assignMarkerLanes(markers.map((m) => m.percentile), minGap), [markers, minGap]);
  const laneCount = Math.max(1, ...lanes.map((lane) => lane + 1));
  const bins = useMemo(() => data?.bins ?? [], [data]);
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const focusBin = focusPct == null ? -1 : binIndexAtPercentile(bins, focusPct);
  const bucket = useMemo(
    () => (hasFullPool && focusBin >= 0 ? bucketPlayers(poolPlayers, bins, focusBin) : []),
    [hasFullPool, focusBin, poolPlayers, bins],
  );
  const nearFocus = useMemo(() => (focusPct == null ? [] : playersNearPercentile(poolPlayers, focusPct, 1)), [focusPct, poolPlayers]);
  const results = useMemo(() => searchExplorerPool(poolPlayers, query), [poolPlayers, query]);
  const median = useMemo(() => poolMedian(poolPlayers), [poolPlayers]);
  const mine = useMemo(
    () => poolPlayers.filter((p) => rosterIds.has(p.player_id) && p.player_id !== me?.player_id),
    [poolPlayers, rosterIds, me],
  );
  const positionLabel = data?.position ?? '';
  const metrics = explorerMetricsFor(positionLabel || undefined, { key: statKey, label: statLabel });

  useEffect(() => {
    trackUse('percentile_explorer', 'opened', { props: { item_kind: statKey } });
    // once per sheet mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tick as the scrub finger crosses into a new bar.
  useEffect(() => {
    if (focusBin >= 0) void Haptics.selectionAsync().catch(() => {});
  }, [focusBin]);

  const changePool = (key: string) => {
    trackUse('percentile_explorer', 'pool_changed', {
      props: { item_kind: metric.key, result: key === 'all' ? 'all' : 'position' },
    });
    setPool(key === 'all' ? 'all' : 'position');
    setState({ status: 'loading' });
    setPickedId(null);
    setSwapped(false);
    setFocusPct(null);
  };

  const changeMetric = (key: string) => {
    const next = metrics.find((m) => m.key === key);
    if (!next || next.key === metric.key) return;
    trackUse('percentile_explorer', 'metric_changed', { props: { item_kind: next.key } });
    setMetric(next);
    setState({ status: 'loading' });
    setFocusPct(null);
    setSwapped(false);
  };

  const pick = (player: ExplorerPlayer) => {
    if (me && player.player_id === me.player_id) return;
    trackUse('percentile_explorer', 'compare_picked', { props: { item_kind: metric.key } });
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setPickedId(player.player_id);
    setPins((prev) => addPin(prev, player.player_id));
    setSwapped(false);
  };

  const setFromX = useCallback((x: number) => {
    const width = chartWidthRef.current;
    if (width <= 0) return;
    setFocusPct(Math.min(100, Math.max(0, (x / width) * 100)));
    setShowAllBucket(false);
  }, []);

  // Drag along the histogram to scrub the percentile axis; a tap picks one bar.
  const scrub = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderTerminationRequest: () => false,
        onPanResponderGrant: (event) => {
          scrubStartX.current = event.nativeEvent.locationX;
          setFromX(scrubStartX.current);
        },
        onPanResponderMove: (_event, gesture) => setFromX(scrubStartX.current + gesture.dx),
      }),
    [setFromX],
  );

  const left = swapped ? comparison : me;
  const right = swapped ? me : comparison;

  const side = (player: ExplorerPlayer) => (
    <View style={styles.side}>
      <PressableScale style={styles.sideId} onPress={() => onOpenPlayer(player)} accessibilityLabel={`Open ${player.name}`}>
        <PlayerAvatar playerId={player.player_id} size={36} />
        <PlayerName name={player.name} style={styles.sideName} />
      </PressableScale>
      <AppText style={styles.sideMeta}>{[player.team, player.position].filter(Boolean).join(' · ')}</AppText>
      <View style={styles.sideStat}>
        <AppText style={styles.sideValue}>{formatExplorerValue(player.value, data?.format)}</AppText>
        <AppText style={[styles.sidePct, { color: percentileColor(player.percentile, colors) }]}>
          {ordinal(player.percentile)}
        </AppText>
      </View>
    </View>
  );

  const renderRows = (players: ExplorerPlayer[], onPress: (player: ExplorerPlayer) => void) =>
    players.map((player) => {
      const isMe = player.player_id === me?.player_id;
      const isPicked = player.player_id === comparison?.player_id;
      return (
        <PressableScale
          key={player.player_id}
          disabled={isMe}
          style={[styles.row, isPicked && styles.rowPicked]}
          onPress={() => onPress(player)}
          accessibilityLabel={`${isMe ? 'Selected player ' : 'Compare with '}${player.name}`}
        >
          <PlayerAvatar playerId={player.player_id} size={32} />
          <View style={styles.rowId}>
            <View style={styles.rowNameLine}>
              <PlayerName name={player.name} style={styles.rowName} />
              {rosterIds.has(player.player_id) ? <AppText style={styles.tag}>MY ROSTER</AppText> : null}
              {isMe ? <AppText style={styles.tag}>YOU</AppText> : null}
            </View>
            <AppText style={styles.rowMeta}>{[player.team, player.position].filter(Boolean).join(' · ')}</AppText>
          </View>
          <AppText style={styles.rowValue}>{formatExplorerValue(player.value, data?.format)}</AppText>
          <View style={[styles.badge, { borderColor: percentileColor(player.percentile, colors) }]}>
            <AppText style={styles.badgeText}>{ordinal(player.percentile)}</AppText>
          </View>
        </PressableScale>
      );
    });

  const bucketShown = showAllBucket ? bucket.slice(0, LIST_CAP) : bucket.slice(0, LIST_PREVIEW);

  return (
    <SheetModal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <SwipeDismissCard style={styles.card} onDismiss={onClose}>
          <View style={styles.headerRow}>
            <View style={styles.headerText}>
              <AppText style={styles.title}>{metric.label} Percentile Explorer</AppText>
              <AppText style={styles.hint}>Drag across the chart or tap a bar to see who sits there.</AppText>
            </View>
            <PressableScale onPress={onClose} style={styles.close} hitSlop={8} accessibilityLabel="Close percentile explorer">
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </PressableScale>
          </View>
          <SheetScrollView style={styles.scroll} keyboardShouldPersistTaps="handled">
            <SegmentedTabBar
              scrollable
              options={metrics.map((m) => ({ key: m.key, label: m.label }))}
              active={metric.key}
              onChange={changeMetric}
            />
            <View style={styles.controlGap} />
            <SegmentedTabBar
              options={[
                { key: 'position', label: positionLabel ? `Same Position (${positionLabel})` : 'Same Position' },
                { key: 'all', label: 'All Players' },
              ]}
              active={pool}
              onChange={changePool}
            />

            {view === 'loading' ? <View style={styles.skeleton} testID="pe-loading" /> : null}
            {view === 'error' ? <ErrorState compact title="Couldn't load this stat" onRetry={() => { setState({ status: 'loading' }); setRetryToken((n) => n + 1); }} /> : null}
            {view === 'insufficient_pool' || view === 'season_unavailable' || view === 'no_data' ? (
              <EmptyState icon="stats-chart-outline" {...explorerEmptyCopy(data?.reason ?? 'no_data', positionLabel)} />
            ) : null}

            {view === 'chart' && me && data ? (
              <>
                <View
                  style={[styles.chart, { height: AXIS_H + BAR_AREA + 8 + laneCount * LANE_STEP }]}
                  onLayout={(event) => {
                    chartWidthRef.current = event.nativeEvent.layout.width;
                    setChartWidth(event.nativeEvent.layout.width);
                  }}
                >
                  <View style={styles.bars} pointerEvents="none">
                    {bins.map((bin, index) => (
                      <View
                        key={index}
                        style={[
                          styles.bar,
                          index === focusBin && styles.barFocus,
                          {
                            left: `${bin.pct_start}%`,
                            width: `${Math.max(0, bin.pct_end - bin.pct_start)}%`,
                            height: Math.max(3, (bin.count / maxCount) * BAR_AREA),
                          },
                        ]}
                      />
                    ))}
                    {focusPct != null ? <View style={[styles.cursor, { left: `${focusPct}%` }]} /> : null}
                  </View>
                  <View
                    style={styles.scrubStrip}
                    {...scrub.panHandlers}
                    accessible
                    accessibilityRole="adjustable"
                    accessibilityLabel={`Scrub ${metric.label} percentile`}
                    accessibilityValue={{ min: 0, max: 100, now: Math.round(focusPct ?? me.percentile) }}
                    accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
                    onAccessibilityAction={(event) => {
                      const step = event.nativeEvent.actionName === 'increment' ? 2 : -2;
                      setFocusPct((prev) => Math.min(100, Math.max(0, (prev ?? me.percentile) + step)));
                    }}
                  />
                  {chartWidth > 0
                    ? markers.map((marker, index) => {
                        const isMe = marker.player_id === me.player_id;
                        const isPicked = !isMe && comparison?.player_id === marker.player_id;
                        const isMine = !isMe && rosterIds.has(marker.player_id);
                        const lift = lanes[index] * LANE_STEP;
                        const x = (marker.percentile / 100) * chartWidth;
                        const boxX = Math.min(chartWidth - MARKER_W, Math.max(0, x - MARKER_W / 2));
                        return (
                          <React.Fragment key={marker.player_id}>
                            <View pointerEvents="none" style={[styles.stem, { left: x, height: BAR_AREA + lift }]} />
                            <PressableScale
                              disabled={isMe}
                              style={[styles.marker, { left: boxX, bottom: AXIS_H + BAR_AREA + lift }]}
                              onPress={() => pick(marker)}
                              accessibilityLabel={`${marker.name}, ${formatExplorerValue(marker.value, data.format)} ${metric.label}, ${ordinal(marker.percentile)} percentile`}
                            >
                              <PlayerName name={marker.name} style={[styles.markerName, (isMe || isMine) && { color: colors.accent }]} />
                              <View style={[styles.face, isPicked && styles.facePicked, isMe && styles.faceMe]}>
                                <PlayerAvatar playerId={marker.player_id} size={isMe ? 36 : 30} />
                              </View>
                              <View style={styles.markerValueRow}>
                                <AppText style={[styles.markerValue, isMe && { color: colors.accent }]}>
                                  {formatExplorerValue(marker.value, data.format)}
                                </AppText>
                                <View style={[styles.badge, { borderColor: percentileColor(marker.percentile, colors) }]}>
                                  <AppText style={styles.badgeText}>{ordinal(marker.percentile)}</AppText>
                                </View>
                                {isMine ? <AppText style={styles.tag}>MY</AppText> : null}
                              </View>
                            </PressableScale>
                          </React.Fragment>
                        );
                      })
                    : null}
                  <View style={styles.axis} pointerEvents="none">
                    {[0, 25, 50, 75, 100].map((tick) => (
                      <AppText key={tick} style={styles.axisTick}>
                        {tick}
                      </AppText>
                    ))}
                  </View>
                </View>
                <AppText style={styles.axisTitle}>{metric.label} percentile</AppText>
                {data.sample_note ? (
                  <AppText style={styles.hint}>{data.sample_note}</AppText>
                ) : data.season ? (
                  <AppText style={styles.hint}>{`Season ${data.season}`}</AppText>
                ) : null}
                {rosterIds.size > 0 && markers.some((m) => rosterIds.has(m.player_id) && m.player_id !== me.player_id) ? (
                  <AppText style={styles.hint}>MY = a player on your roster</AppText>
                ) : null}

                <Tabs
                  id="percentile"
                  tabs={percentileTabs({ hasFullPool, mineCount: mine.length }).map((tab) => ({
                    key: tab.key,
                    label: tab.label,
                    render: () =>
                      tab.key === 'bucket' ? (
                    focusBin >= 0 && bins[focusBin] ? (
                  <View style={styles.section}>
                    <View style={styles.sectionHead}>
                      <AppText style={styles.sectionTitle}>
                        {bins[focusBin].value_start === bins[focusBin].value_end
                          ? formatExplorerValue(bins[focusBin].value_start, data.format)
                          : `${formatExplorerValue(bins[focusBin].value_start, data.format)} to ${formatExplorerValue(bins[focusBin].value_end, data.format)}`}
                        {` · ${bucket.length} ${bucket.length === 1 ? 'player' : 'players'}`}
                      </AppText>
                      {focusPct != null && nearFocus[0] ? (
                        <AppText style={styles.sectionTitle}>About the {ordinal(Math.round(focusPct))} percentile</AppText>
                      ) : null}
                    </View>
                    {bucket.length === 0 ? (
                      <AppText style={styles.hint}>Nobody sits in this bucket.</AppText>
                    ) : (
                      <View style={styles.list}>{renderRows(bucketShown, pick)}</View>
                    )}
                    {bucket.length > LIST_PREVIEW ? (
                      <PressableScale style={styles.more} onPress={() => setShowAllBucket((v) => !v)}>
                        <AppText style={styles.moreText}>
                          {showAllBucket ? 'Show fewer' : `Show ${Math.min(bucket.length, LIST_CAP) - LIST_PREVIEW} more`}
                        </AppText>
                      </PressableScale>
                    ) : null}
                  </View>
                    ) : (
                      <AppText style={styles.hint}>Drag across the chart or tap a bar to list the players in that bucket.</AppText>
                    )
                      ) : tab.key === 'find' ? (
                  <View style={styles.section}>
                    <Input
                      value={query}
                      onChangeText={setQuery}
                      placeholder={pool === 'all' ? 'Search any player to add' : `Search ${positionLabel || 'position'} players to add`}
                      accessibilityLabel="Search players to add to the chart"
                      autoCorrect={false}
                      autoCapitalize="none"
                      returnKeyType="search"
                    />
                    {query.trim().length >= 2 ? (
                      results.length > 0 ? (
                        <View style={styles.list}>
                          {renderRows(results, (player) => {
                            pick(player);
                            setQuery('');
                          })}
                        </View>
                      ) : (
                        <AppText style={styles.hint}>
                          {`No ${pool === 'all' ? '' : `${positionLabel || 'position'} `}player with a ranked value matches that.${pool === 'position' ? ' Try All Players.' : ''}`}
                        </AppText>
                      )
                    ) : null}
                  </View>
                      ) : (
                  <View style={styles.section}>
                    <View style={styles.sectionHead}>
                      <AppText style={styles.sectionTitle}>Your roster here</AppText>
                      <AppText style={styles.sectionTitle}>{mine.length}</AppText>
                    </View>
                    <View style={styles.list}>{renderRows(mine.slice(0, LIST_CAP), pick)}</View>
                  </View>
                      ),
                  }))}
                />
              </>
            ) : null}
          </SheetScrollView>
          {view === 'chart' && me && data && left && right ? (
            <View style={styles.pinned}>
              <View style={styles.compare}>
                {side(left)}
                <View style={styles.delta}>
                  <PressableScale style={styles.swap} onPress={() => setSwapped((value) => !value)} accessibilityLabel="Swap comparison">
                    <Ionicons name="swap-horizontal" size={18} color={colors.textSecondary} />
                  </PressableScale>
                  <AppText style={styles.deltaValue}>{formatExplorerDelta(left.value, right.value, data.format)}</AppText>
                  <AppText style={styles.deltaLabel}>vs comparison</AppText>
                  {median != null ? (
                    <AppText style={styles.deltaLabel} testID="pe-median">
                      Median {formatExplorerValue(median, data.format)}
                    </AppText>
                  ) : null}
                </View>
                {side(right)}
              </View>
            </View>
          ) : null}
        </SwipeDismissCard>
      </View>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    card: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      maxHeight: '92%',
      padding: spacing.lg,
    },
    scroll: { flexGrow: 0, flexShrink: 1 },
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.md },
    headerText: { flex: 1, paddingRight: spacing.md },
    close: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', marginTop: -spacing.sm, marginRight: -spacing.sm },
    title: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    hint: { fontSize: 13.5, color: colors.textTertiary, marginTop: 2 },
    controlGap: { height: spacing.sm },
    skeleton: { height: 260, marginTop: spacing.md, borderRadius: radii.md, backgroundColor: colors.surface, opacity: 0.6 },
    chart: { marginTop: spacing.md, width: '100%' },
    bars: {
      position: 'absolute',
      left: 0,
      right: 0,
      bottom: AXIS_H,
      height: BAR_AREA,
      borderBottomWidth: 2,
      borderBottomColor: colors.accent,
    },
    bar: { position: 'absolute', bottom: 0, backgroundColor: colors.border, borderTopLeftRadius: 2, borderTopRightRadius: 2, borderRightWidth: 1, borderRightColor: colors.backgroundElevated },
    barFocus: { backgroundColor: colors.accent },
    cursor: { position: 'absolute', top: 0, bottom: 0, width: 2, marginLeft: -1, backgroundColor: colors.accentStrong },
    scrubStrip: { position: 'absolute', left: 0, right: 0, bottom: AXIS_H, height: BAR_AREA },
    axis: { position: 'absolute', left: 0, right: 0, bottom: 0, height: AXIS_H - 2, flexDirection: 'row', justifyContent: 'space-between' },
    axisTick: { fontSize: 12.5, color: colors.textTertiary },
    axisTitle: { textAlign: 'center', fontSize: 12, letterSpacing: 1, textTransform: 'uppercase', color: colors.textTertiary, marginBottom: spacing.sm },
    stem: { position: 'absolute', bottom: AXIS_H, width: 1, backgroundColor: colors.border, opacity: 0.7 },
    marker: { position: 'absolute', width: MARKER_W, alignItems: 'center', minHeight: 44 },
    markerName: { fontSize: 12.5, fontWeight: '600', color: colors.textSecondary, maxWidth: MARKER_W },
    markerValueRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    markerValue: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    face: { borderRadius: 20 },
    faceMe: { shadowColor: colors.accent, shadowOpacity: 0.9, shadowRadius: 8, shadowOffset: { width: 0, height: 0 } },
    facePicked: { borderWidth: 2, borderColor: colors.premium },
    badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 6, backgroundColor: colors.surface },
    badgeText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    tag: { fontSize: 12, fontWeight: '800', letterSpacing: 0.4, color: colors.accent, backgroundColor: colors.accentMuted, borderRadius: 999, paddingHorizontal: 5, overflow: 'hidden' },
    section: { gap: spacing.xs, marginBottom: spacing.md },
    sectionHead: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
    sectionTitle: { fontSize: 13.5, fontWeight: '700', color: colors.textSecondary },
    list: { borderWidth: 1, borderColor: colors.cardBorder, borderRadius: radii.md, overflow: 'hidden' },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 52, paddingHorizontal: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.cardBorder },
    rowPicked: { backgroundColor: colors.accentMuted },
    rowId: { flex: 1, minWidth: 0 },
    rowNameLine: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    rowName: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    rowMeta: { fontSize: 12.5, color: colors.textTertiary },
    rowValue: { fontSize: 16.5, fontWeight: '800', color: colors.textPrimary },
    more: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    moreText: { fontSize: 14.5, fontWeight: '700', color: colors.accent },
    pinned: { paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.cardBorder },
    compare: { flexDirection: 'row', alignItems: 'stretch', gap: spacing.sm },
    side: { flex: 1, padding: spacing.sm, borderWidth: 1, borderColor: colors.cardBorder, borderRadius: radii.md, backgroundColor: colors.surface },
    sideId: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minHeight: 44 },
    sideName: { flex: 1, fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    sideMeta: { fontSize: 12.5, color: colors.textTertiary, marginTop: 2 },
    sideStat: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.xs },
    sideValue: { fontSize: 21, fontWeight: '800', color: colors.textPrimary },
    sidePct: { fontSize: 12.5, fontWeight: '700' },
    delta: { alignItems: 'center', justifyContent: 'center', gap: 2 },
    swap: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
    deltaValue: { fontSize: 17, fontWeight: '800', color: colors.accent },
    deltaLabel: { fontSize: 12, color: colors.textTertiary },
  });
}

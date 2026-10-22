import { Ionicons } from '@expo/vector-icons';
import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import PlayerAvatar from './PlayerAvatar';
import SegmentedTabBar from './SegmentedTabBar';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  assignMarkerLanes,
  defaultComparison,
  explorerEmptyCopy,
  explorerViewState,
  formatExplorerDelta,
  formatExplorerValue,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from '../lib/percentileExplorer';
import { ordinal, percentileColor } from '../lib/percentile';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

const LANE_COUNT = 3;
const LANE_STEP = 84;
const BAR_AREA = 64;
const AXIS_H = 22;
const MARKER_W = 58;

type LoadState = { status: 'loading' | 'error' } | { status: 'ready'; data: PercentileExplorerResponse };

/**
 * Percentile Explorer: bottom sheet behind one stat tile on Player Detail.
 * Same data as web (GET /v1/players/{id}/percentile-explorer). The histogram is
 * plain Views (no chart library); markers are real nearby players.
 */
export default function PercentileExplorerSheet({
  playerId,
  statKey,
  statLabel,
  onClose,
  onOpenPlayer,
}: {
  playerId: string;
  statKey: string;
  statLabel: string;
  onClose: () => void;
  onOpenPlayer: (player: ExplorerPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [pool, setPool] = useState<'position' | 'all'>('position');
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [swapped, setSwapped] = useState(false);
  const [chartWidth, setChartWidth] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getPercentileExplorer(playerId, statKey, pool)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, statKey, pool]);

  const data = state.status === 'ready' ? state.data : null;
  const view = explorerViewState(state.status, data);
  const me = data?.player ?? null;
  const nearby = useMemo(() => data?.nearby ?? [], [data]);
  const comparison = me ? (nearby.find((p) => p.player_id === pickedId) ?? defaultComparison(me, nearby)) : null;
  const markers = useMemo(() => (me ? [...nearby, me].sort((a, b) => a.percentile - b.percentile) : []), [me, nearby]);
  const lanes = useMemo(() => assignMarkerLanes(markers.map((m) => m.percentile)), [markers]);
  const maxCount = Math.max(1, ...(data?.bins ?? []).map((b) => b.count));
  const positionLabel = data?.position ?? '';

  const changePool = (key: string) => {
    setPool(key === 'all' ? 'all' : 'position');
    setState({ status: 'loading' });
    setPickedId(null);
    setSwapped(false);
  };

  const left = swapped ? comparison : me;
  const right = swapped ? me : comparison;

  const side = (player: ExplorerPlayer) => (
    <View style={styles.side}>
      <TouchableOpacity style={styles.sideId} onPress={() => onOpenPlayer(player)} accessibilityLabel={`Open ${player.name}`}>
        <PlayerAvatar playerId={player.player_id} size={36} />
        <AppText style={styles.sideName} numberOfLines={1}>
          {player.name}
        </AppText>
      </TouchableOpacity>
      <AppText style={styles.sideMeta}>{[player.team, player.position].filter(Boolean).join(' · ')}</AppText>
      <AppText style={styles.sideValue}>{formatExplorerValue(player.value, data?.format)}</AppText>
      <AppText style={[styles.sidePct, { color: percentileColor(player.percentile, colors) }]}>
        {ordinal(player.percentile)} percentile
      </AppText>
    </View>
  );

  return (
    <SheetModal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <SwipeDismissCard style={styles.card} onDismiss={onClose}>
          <View style={styles.headerRow}>
            <View style={styles.headerText}>
              <AppText style={styles.title}>{statLabel} Percentile Explorer</AppText>
              <AppText style={styles.hint}>Tap a player to compare where he sits.</AppText>
            </View>
            <TouchableOpacity onPress={onClose} hitSlop={8} accessibilityLabel="Close percentile explorer">
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <SheetScrollView>
            <SegmentedTabBar
              options={[
                { key: 'position', label: positionLabel ? `Same Position (${positionLabel})` : 'Same Position' },
                { key: 'all', label: 'All Players' },
              ]}
              active={pool}
              onChange={changePool}
            />
            <View style={styles.scopeRow}>
              <AppText style={styles.scopeText}>{data?.season ? `Season ${data.season}` : 'Season'}</AppText>
            </View>

            {view === 'loading' ? <View style={styles.skeleton} testID="pe-loading" /> : null}
            {view === 'error' ? <EmptyState icon="cloud-offline-outline" title="Couldn't load this stat" subtitle="Try again in a moment." /> : null}
            {view === 'insufficient_pool' || view === 'season_unavailable' || view === 'no_data' ? (
              <EmptyState icon="stats-chart-outline" {...explorerEmptyCopy(data?.reason ?? 'no_data', positionLabel)} />
            ) : null}

            {view === 'chart' && me && data ? (
              <>
                <View
                  style={[styles.chart, { height: AXIS_H + BAR_AREA + LANE_COUNT * LANE_STEP }]}
                  onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}
                >
                  <View style={styles.bars}>
                    {(data.bins ?? []).map((bin, index) => (
                      <View
                        key={index}
                        style={[
                          styles.bar,
                          {
                            left: `${bin.pct_start}%`,
                            width: `${Math.max(0, bin.pct_end - bin.pct_start)}%`,
                            height: Math.max(2, (bin.count / maxCount) * BAR_AREA),
                          },
                        ]}
                      />
                    ))}
                  </View>
                  {chartWidth > 0
                    ? markers.map((marker, index) => {
                        const isMe = marker.player_id === me.player_id;
                        const isPicked = !isMe && comparison?.player_id === marker.player_id;
                        const lift = lanes[index] * LANE_STEP;
                        const x = (marker.percentile / 100) * chartWidth;
                        const boxX = Math.min(chartWidth - MARKER_W, Math.max(0, x - MARKER_W / 2));
                        return (
                          <React.Fragment key={marker.player_id}>
                            <View style={[styles.stem, { left: x, height: BAR_AREA + lift }]} />
                            <TouchableOpacity
                              disabled={isMe}
                              style={[styles.marker, { left: boxX, bottom: AXIS_H + BAR_AREA + lift }]}
                              onPress={() => {
                                setPickedId(marker.player_id);
                                setSwapped(false);
                              }}
                              accessibilityLabel={`${marker.name}, ${formatExplorerValue(marker.value, data.format)} ${statLabel}, ${ordinal(marker.percentile)} percentile`}
                            >
                              <AppText style={[styles.markerName, isMe && { color: colors.accent }]} numberOfLines={1}>
                                {marker.name}
                              </AppText>
                              <AppText style={[styles.markerValue, isMe && { color: colors.accent }]}>
                                {formatExplorerValue(marker.value, data.format)}
                              </AppText>
                              <View style={[styles.face, isPicked && styles.facePicked, isMe && styles.faceMe]}>
                                <PlayerAvatar playerId={marker.player_id} size={isMe ? 36 : 30} />
                              </View>
                              <View style={[styles.badge, { borderColor: percentileColor(marker.percentile, colors) }]}>
                                <AppText style={styles.badgeText}>{ordinal(marker.percentile)}</AppText>
                              </View>
                            </TouchableOpacity>
                          </React.Fragment>
                        );
                      })
                    : null}
                  <View style={styles.axis}>
                    {[0, 25, 50, 75, 100].map((tick) => (
                      <AppText key={tick} style={styles.axisTick}>
                        {tick}
                      </AppText>
                    ))}
                  </View>
                </View>
                <AppText style={styles.axisTitle}>{statLabel} percentile</AppText>

                {left && right ? (
                  <View style={styles.compare}>
                    {side(left)}
                    <View style={styles.delta}>
                      <TouchableOpacity
                        style={styles.swap}
                        onPress={() => setSwapped((value) => !value)}
                        accessibilityLabel="Swap comparison"
                      >
                        <Ionicons name="swap-horizontal" size={18} color={colors.textSecondary} />
                      </TouchableOpacity>
                      <AppText style={styles.deltaValue}>{formatExplorerDelta(left.value, right.value, data.format)}</AppText>
                      <AppText style={styles.deltaLabel}>vs comparison</AppText>
                    </View>
                    {side(right)}
                  </View>
                ) : null}
              </>
            ) : null}
          </SheetScrollView>
        </SwipeDismissCard>
      </View>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    card: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      maxHeight: '92%',
      padding: spacing.lg,
    },
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.md },
    headerText: { flex: 1, paddingRight: spacing.md },
    title: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    hint: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
    scopeRow: { flexDirection: 'row', marginTop: spacing.sm },
    scopeText: { fontSize: 12, fontWeight: '700', color: colors.accent },
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
    axis: { position: 'absolute', left: 0, right: 0, bottom: 0, height: AXIS_H - 2, flexDirection: 'row', justifyContent: 'space-between' },
    axisTick: { fontSize: 11, color: colors.textTertiary },
    axisTitle: { textAlign: 'center', fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', color: colors.textTertiary, marginBottom: spacing.md },
    stem: { position: 'absolute', bottom: AXIS_H, width: 1, backgroundColor: colors.border, opacity: 0.7 },
    marker: { position: 'absolute', width: MARKER_W, alignItems: 'center' },
    markerName: { fontSize: 10, color: colors.textTertiary, maxWidth: MARKER_W },
    markerValue: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    face: { borderRadius: 20 },
    faceMe: { shadowColor: colors.accent, shadowOpacity: 0.9, shadowRadius: 8, shadowOffset: { width: 0, height: 0 } },
    facePicked: { borderWidth: 2, borderColor: colors.premium },
    badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 6, backgroundColor: colors.surface },
    badgeText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
    compare: { flexDirection: 'row', alignItems: 'stretch', gap: spacing.sm },
    side: { flex: 1, padding: spacing.sm, borderWidth: 1, borderColor: colors.cardBorder, borderRadius: radii.md, backgroundColor: colors.surface },
    sideId: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    sideName: { flex: 1, fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    sideMeta: { fontSize: 11, color: colors.textTertiary, marginTop: 2 },
    sideValue: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    sidePct: { fontSize: 11, fontWeight: '700' },
    delta: { alignItems: 'center', justifyContent: 'center', gap: 2 },
    swap: { width: 32, height: 32, borderRadius: 16, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
    deltaValue: { fontSize: 16, fontWeight: '800', color: colors.accent },
    deltaLabel: { fontSize: 10, color: colors.textTertiary },
  });
}

import React, { useEffect, useMemo, useReducer, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import EmptyState from './EmptyState';
import Input from './Input';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPager, SimPlayerLine, SimSheet, SimStat, SimToneBadge, createSimStyles, useSimDebounced } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import {
  SIM_PAGE_SIZE,
  SIM_POSITIONS,
  SIM_SORT_OPTIONS,
  SIM_STATUS_OPTIONS,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtAge,
  simFmtProjection,
  simFmtPts,
  simFmtValue,
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
          {items.map((player) => (
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
                  <SimStat label="Value" value={simFmtValue(player.value)} />
                  {actions ? actions(player) : null}
                </>
              }
            />
          ))}
        </View>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: 'page', value: page })} />
    </View>
  );
}

/** Player sheet: this week's projection and band, week-by-week outlook, results so far, news. */
export function SimPlayerSheet({ gameId, player, onClose, actions }: { gameId: string; player: SimGamePlayer; onClose: () => void; actions?: ReactNode }) {
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
  return (
    <SimSheet title={player.name} onClose={onClose}>
      <View style={common.row}>
        <PlayerAvatar playerId={player.id} size={56} />
        <View style={[common.grow, common.tight]}>
          <View style={common.wrapRow}>
            <PositionBadge position={live.pos} />
            <AppText style={common.small}>{live.team ?? 'Free agent'}</AppText>
            {simFmtAge(live.age) ? <AppText style={common.small}>Age {simFmtAge(live.age)}</AppText> : null}
          </View>
          <View style={common.wrapRow}>
            {status ? <SimToneBadge label={status.label} tone={status.tone} /> : null}
            {live.owner ? <SimToneBadge label={simOwnerLabel(live.owner)} tone={simOwnerTone(live.owner)} /> : null}
          </View>
        </View>
      </View>
      <View style={styles.statGrid}>
        <View style={styles.statCell}>
          <AccentCard accent={colors.accent} compact>
            <AppText style={common.muted}>This week</AppText>
            <AppText style={styles.statBig}>{simFmtPts(live.projection)}</AppText>
            <AppText style={common.muted}>
              {simFmtPts(live.floor)}-{simFmtPts(live.ceiling)}
            </AppText>
          </AccentCard>
        </View>
        <View style={styles.statCell}>
          <AccentCard accent={colors.premium} compact>
            <AppText style={common.muted}>Value</AppText>
            <AppText style={styles.statBig}>{simFmtValue(live.value)}</AppText>
            <AppText style={common.muted}>ADP {simFmtValue(live.adp)}</AppText>
          </AccentCard>
        </View>
        <View style={styles.statCell}>
          <AccentCard accent={colors.success} compact>
            <AppText style={common.muted}>Season</AppText>
            <AppText style={styles.statBig}>{simFmtPts(live.season_points ?? 0)}</AppText>
            <AppText style={common.muted}>{live.games ?? 0} games</AppText>
          </AccentCard>
        </View>
      </View>
      {actions ? <View style={common.wrapRow}>{actions}</View> : null}
      {failed ? (
        <AppText style={common.small}>The full outlook did not load. Close and reopen to retry.</AppText>
      ) : !detail ? (
        <SkeletonCard rows={2} />
      ) : (
        <>
          {weeks.length > 0 ? (
            <View style={common.stack}>
              <SectionHeading title="Week by week" caption="Projection with its floor-to-ceiling band for each remaining week." />
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
          ) : null}
          {(detail.history ?? []).length > 0 ? (
            <View style={common.stack}>
              <SectionHeading title="Results so far" />
              <View style={common.wrapRow}>
                {detail.history!.map((h) => (
                  <View key={h.week} style={styles.chip}>
                    <AppText style={common.muted}>W{h.week} </AppText>
                    <AppText style={common.bodyStrong}>{simFmtPts(h.points)}</AppText>
                  </View>
                ))}
              </View>
            </View>
          ) : null}
          {(detail.news ?? []).length > 0 ? (
            <View style={common.stack}>
              <SectionHeading title="News" />
              {detail.news!.map((n, i) => (
                <AppText key={i} style={common.body}>
                  <AppText style={common.muted}>Week {n.week} · </AppText>
                  {n.text}
                </AppText>
              ))}
            </View>
          ) : null}
        </>
      )}
    </SimSheet>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    statGrid: { flexDirection: 'row', gap: spacing.sm },
    statCell: { flex: 1, minWidth: 0 },
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

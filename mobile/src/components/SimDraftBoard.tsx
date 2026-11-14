import React, { useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import EmptyState from './EmptyState';
import Input from './Input';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPager, createSimStyles, useSimDebounced } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import PlayerListRow from './PlayerListRow';
import type { PlayerListDensity, PlayerListTag } from '../lib/playerListRow';
import { SIM_DRAFT_SORTS, simCycleSort, simDraftMeta, simDraftRowChips, simListStats } from '../lib/simDraft';
import { SIM_WINDOW_STEP, simWindow } from '../lib/simLayout';
import {
  SIM_PAGE_SIZE,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simHeadshotId,
  simPageCount,
  simPlayerInitials,
  simPlayerIsGenerated,
  type SimGamePlayer,
  type SimPlayerSort,
  type SimPosFilter,
} from '../lib/simGame';
import { radii, type ThemeColors } from '../theme';


type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * An icon-only action button (queue / draft / reorder / remove). Instant
 * feedback: it dims and disables itself in the same press (a ref guard blocks a
 * double tap) and, when onPress returns a promise, stays disabled until it
 * settles. Light haptic on press.
 */
export function SimDraftIconButton({
  icon,
  label,
  onPress,
  active = false,
  disabled = false,
  primary = false,
  size = 40,
  width,
}: {
  icon: IconName;
  label: string;
  onPress: () => void | Promise<unknown>;
  active?: boolean;
  disabled?: boolean;
  primary?: boolean;
  size?: number;
  width?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const inflight = useRef(false);
  const [pending, setPending] = useState(false);
  const off = disabled || pending;
  const tint = off ? colors.textTertiary : primary ? colors.onAccent : active ? colors.accent : colors.textSecondary;
  const run = async () => {
    if (inflight.current || disabled) return;
    inflight.current = true;
    setPending(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    try {
      await onPress();
    } finally {
      inflight.current = false;
      setPending(false);
    }
  };
  return (
    <Pressable
      onPress={run}
      disabled={off}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: off, selected: active, busy: pending }}
      style={({ pressed }) => [
        styles.iconButton,
        { width: width ?? size, height: size, opacity: pressed ? 0.7 : 1, transform: [{ scale: pressed ? 0.95 : 1 }] },
        active && { backgroundColor: colors.accentMuted },
        primary && { backgroundColor: colors.accent },
      ]}
    >
      <Ionicons name={pending ? 'hourglass-outline' : icon} size={20} color={tint} />
    </Pressable>
  );
}

/**
 * One sim player-list row: a thin mapping from a sim player onto the shared
 * PlayerListRow (docs/player-card.md, `list` variant). Draft Players/Board, the
 * rookie draft and the Players / Waivers tabs render through it. Bye is always
 * shown (simDraftMeta), an injury is a chip + dot (never a dimmed row) and every
 * number is a labeled pill (simListStats).
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
  onGeneratedInfo,
  week = 0,
  drafted = false,
  tags,
  extra,
  chipsExtra,
  density,
  hideRookie = false,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
  /** Opens the generated-class notice; shows a small info glyph on simulated rookies. */
  onGeneratedInfo?: () => void;
  /** Current game week (0 while drafting): decides which byes count as "soon". */
  week?: number;
  /** Optimistic: just picked; the row slides out while the server confirms. */
  drafted?: boolean;
  tags?: PlayerListTag[];
  extra?: ReactNode;
  /** Small inline controls at the end of the chips line (a Queue toggle). */
  chipsExtra?: ReactNode;
  density?: PlayerListDensity;
  /** A rookie-only draft: every player is a rookie, so the "Rookie" tag adds nothing. */
  hideRookie?: boolean;
}) {
  const [chip] = simDraftRowChips(player);
  return (
    <PlayerListRow
      testID="draft-row"
      name={player.name}
      position={player.pos}
      headshotId={simHeadshotId(player)}
      fallbackLabel={simPlayerInitials(player)}
      meta={simDraftMeta(player, week).filter((m) => !(hideRookie && m.key === 'rookie'))}
      chip={chip ? { label: chip.label, tone: chip.tone } : null}
      hurt={player.status === 'out'}
      stats={simListStats(player)}
      tags={tags}
      extra={extra}
      chipsExtra={chipsExtra}
      actions={actions}
      density={density}
      done={drafted}
      onSimInfo={onGeneratedInfo && simPlayerIsGenerated(player) ? onGeneratedInfo : undefined}
      onOpen={onOpen ? () => onOpen(player) : undefined}
      openLabel={`${player.name}, ${player.pos}. Open player details`}
    />
  );
}

/** The draft board: search, shared segmented position + sort strips and fixed-grid rows (free agents only). */
export function SimDraftBoard({
  gameId,
  positions,
  onOpen,
  actions,
  chipsExtra,
  refreshKey = 0,
  onItems,
  week = 0,
  draftedIds,
}: {
  gameId: string;
  /** Filter segments after "All" (simFilterPositionsFor): positions plus FLEX / SUPERFLEX. */
  positions: { label: string; value: SimPosFilter }[];
  week?: number;
  /** Players picked optimistically and still awaiting the server. */
  draftedIds?: string[];
  onOpen: (player: SimGamePlayer) => void;
  actions?: (player: SimGamePlayer) => ReactNode;
  chipsExtra?: (player: SimGamePlayer) => ReactNode;
  refreshKey?: number;
  onItems?: (items: SimGamePlayer[]) => void;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [filter, dispatch] = useReducer(simFilterReducer, simDefaultFilter({ status: 'available', sort: 'adp' }));
  const [text, setText] = useState('');
  const debounced = useSimDebounced(text, PLAYER_SEARCH_DEBOUNCE_MS);
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
    dispatch({ type: 'q', value: debounced });
  }, [debounced]);

  const query = useMemo(() => simFilterQuery({ ...filter, status: 'available' }), [filter]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, query, refreshKey, attempt]);

  return (
    <View style={common.stack}>
      <View>
        <Ionicons name="search-outline" size={18} color={colors.textTertiary} style={styles.searchIcon} />
        <Input
          value={text}
          onChangeText={setText}
          placeholder="Search players or NFL teams"
          accessibilityLabel="Search players"
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
          clearButtonMode="while-editing"
          style={styles.searchInput}
        />
      </View>
      {/* One compact row: position filter and a one-tap sort cycle together (not a strip each). */}
      <View style={styles.filterRow} testID="draft-filters">
        <View style={styles.filterGrow}>
          <SegmentedTabBar<string>
            scrollable
            options={[{ key: '', label: 'All' }, ...positions.map((p) => ({ key: p.value as string, label: p.label }))]}
            active={filter.pos}
            onChange={(key) => dispatch({ type: 'pos', value: key as SimPosFilter | '' })}
          />
        </View>
        <Pressable
          onPress={() => dispatch({ type: 'sort', value: simCycleSort(filter.sort) })}
          accessibilityRole="button"
          accessibilityLabel={`Sort players, now ${SIM_DRAFT_SORTS.find((o) => o.value === filter.sort)?.label ?? 'ADP'}. Tap to change`}
          style={styles.sortButton}
        >
          <AppText style={styles.sortText}>{SIM_DRAFT_SORTS.find((o) => o.value === filter.sort)?.label ?? 'ADP'}</AppText>
          <Ionicons name="swap-vertical" size={14} color={colors.textSecondary} />
        </Pressable>
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
        <EmptyState icon="search-outline" title="No players left that match" subtitle="Try a different search or filter." />
      ) : (
        <View style={{ opacity: state === 'loading' ? 0.6 : 1 }}>
          <AppText style={common.muted} accessibilityLiveRegion="polite">
            {total} player{total === 1 ? '' : 's'} left
          </AppText>
          <AppText style={styles.scaleNote}>OVR is his rank at his position, same as everywhere. EDGE: green = steal, red = reach (the model vs ADP).</AppText>
          {rows.shown.map((player) => (
            <SimDraftRow key={player.id} player={player} onOpen={onOpen} week={week} drafted={draftedIds?.includes(player.id)} actions={actions ? actions(player) : null} chipsExtra={chipsExtra ? chipsExtra(player) : undefined} />
          ))}
          {rows.remaining > 0 ? (
            <Pressable onPress={() => setWin({ key: windowKey, n: visible + SIM_WINDOW_STEP })} accessibilityRole="button" style={styles.showMore}>
              <AppText style={styles.showMoreText}>
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

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    iconButton: {
      borderRadius: radii.md,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.glassInset,
    },
    filterRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    filterGrow: { flex: 1, minWidth: 0 },
    sortButton: { minHeight: 44, minWidth: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingHorizontal: 10, borderRadius: radii.pill, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, backgroundColor: colors.glassInset },
    sortText: { fontSize: 13, fontWeight: '800', color: colors.textPrimary },
    scaleNote: { fontSize: 12, color: colors.textTertiary, paddingBottom: 2 },
    showMore: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    showMoreText: { fontSize: 14, fontWeight: '800', color: colors.accent },
    searchIcon: { position: 'absolute', left: 12, top: 13, zIndex: 1 },
    searchInput: { paddingLeft: 38 },
  });
}

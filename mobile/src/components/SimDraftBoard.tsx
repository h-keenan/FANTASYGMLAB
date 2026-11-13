import React, { useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Animated, Pressable, StyleSheet, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import EmptyState from './EmptyState';
import Input from './Input';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimGeneratedChip } from './SimGameDynastyParts';
import { SimPager, createSimStyles, simToneColor, useSimDebounced } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import { simBoardEdge, simBoardProjection, simDraftMeta, simDraftRowChips } from '../lib/simDraft';
import { SIM_WINDOW_STEP, simWindow } from '../lib/simLayout';
import {
  SIM_PAGE_SIZE,
  simDefaultFilter,
  simFilterQuery,
  simFilterReducer,
  simFmtPts,
  simFmtValue,
  simHeadshotId,
  simPageCount,
  simPlayerInitials,
  simPlayerIsGenerated,
  type SimGamePlayer,
  type SimPlayerSort,
  type SimPosFilter,
} from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

const SORTS: { key: SimPlayerSort; label: string }[] = [
  { key: 'adp', label: 'ADP' },
  { key: 'projection', label: 'Proj' },
  { key: 'value', label: 'Value' },
];

const BADGE_W = 34;
const AVATAR = 40;
/** Stat column widths shared by the header and every row's stat strip: Proj, Value, ADP, Edge. */
const STAT_COLS = [44, 40, 36, 44] as const;

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
 * One draft-board row, built for a 390pt phone (~70pt tall). Line 1: position
 * badge, 40pt photo, full name (a size smaller for long names before it
 * truncates), the red OUT chip only for injured players, and the actions. Line
 * 2 (muted): TEAM · Age · Bye N. The bye is ALWAYS shown (see simDraftMeta) and
 * turns warning-colored only when it is within the next 3 game weeks. Line 3:
 * stat strip in fixed columns matching the header; Edge is an arrow chip only
 * when the gap is 3+ spots. An injured row is never dimmed.
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
  onGeneratedInfo,
  week = 0,
  drafted = false,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
  /** Opens the generated-class notice; shows a small chip on simulated rookies. */
  onGeneratedInfo?: () => void;
  /** Current game week (0 while drafting): decides which byes count as "soon". */
  week?: number;
  /** Optimistic: just picked; the row flashes and slides out while the server confirms. */
  drafted?: boolean;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const edge = positionColor(player.pos, isDark, colors.borderStrong);
  const chips = simDraftRowChips(player);
  const meta = simDraftMeta(player, week);
  const delta = simBoardEdge(player);
  const proj = simBoardProjection(player);
  const out = player.status === 'out';
  const slide = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!drafted) {
      slide.setValue(0);
      return;
    }
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (cancelled) return;
      Animated.timing(slide, { toValue: 1, duration: reduce ? 120 : 240, useNativeDriver: true }).start();
    });
    return () => {
      cancelled = true;
    };
  }, [drafted, slide]);
  const identity = (
    <View style={styles.identity}>
      <View style={styles.badgeSlot}>
        <PositionBadge position={player.pos} />
      </View>
      <View style={styles.avatarSlot}>
        <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={AVATAR} />
        {out ? <View style={styles.outDot} /> : null}
      </View>
      <View style={styles.nameCol}>
        <View style={styles.nameRow}>
          <AppText style={[styles.name, player.name.length > 18 && { fontSize: 13 }]} numberOfLines={1}>
            {player.name}
          </AppText>
          {chips.map((chip) => (
            <ToneBadge key={chip.key} label={chip.label.toUpperCase()} color={simToneColor(chip.tone, colors)} size="xs" />
          ))}
        </View>
        <AppText style={styles.meta} testID="draft-meta">
          {meta.map((part, i) => (
            <AppText key={part.key} style={[styles.meta, part.tone && { color: simToneColor(part.tone, colors) }, part.tone === 'warning' && { fontWeight: '700' }]}>
              {i > 0 ? ' · ' : ''}
              {part.text}
            </AppText>
          ))}
        </AppText>
      </View>
    </View>
  );
  return (
    <Animated.View
      style={[
        styles.row,
        { borderLeftColor: edge },
        drafted && { opacity: slide.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ translateX: slide.interpolate({ inputRange: [0, 1], outputRange: [0, 24] }) }] },
      ]}
      pointerEvents={drafted ? 'none' : 'auto'}
      testID="draft-row"
    >
      <View style={styles.rowTop}>
        {onOpen ? (
          <Pressable style={styles.open} onPress={() => onOpen(player)} accessibilityRole="button" accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}>
            {identity}
          </Pressable>
        ) : (
          <View style={styles.open}>{identity}</View>
        )}
        {drafted ? (
          <AppText style={styles.draftedText} accessibilityLiveRegion="polite">
            Drafted ✓
          </AppText>
        ) : actions ? (
          <View style={styles.actions}>{actions}</View>
        ) : null}
      </View>
      <View style={styles.statsRow}>
        <View style={{ flex: 1, minWidth: 0 }}>{onGeneratedInfo && simPlayerIsGenerated(player) ? <SimGeneratedChip label="Generated" onInfo={onGeneratedInfo} compact /> : null}</View>
        <AppText style={[styles.stat, { width: STAT_COLS[0] }]} accessibilityHint={proj.discounted ? 'Per-game projection, out this week.' : undefined}>
          {simFmtPts(proj.value)}
        </AppText>
        <AppText style={[styles.stat, { width: STAT_COLS[1] }]}>{simFmtValue(player.value)}</AppText>
        <AppText style={[styles.stat, { width: STAT_COLS[2] }]}>{simFmtValue(player.adp)}</AppText>
        <View style={[styles.statCell, { width: STAT_COLS[3] }]}>
          {delta ? (
            <View style={[styles.deltaChip, { backgroundColor: `${simToneColor(delta.tone, colors)}29` }]}>
              <AppText
                style={[styles.deltaText, { color: simToneColor(delta.tone, colors) }]}
                accessibilityLabel={delta.tone === 'success' ? `Steal, ${Math.abs(delta.delta)} spots` : `Reach, ${Math.abs(delta.delta)} spots`}
              >
                {delta.tone === 'success' ? '▲' : '▼'}
                {Math.abs(delta.delta)}
              </AppText>
            </View>
          ) : null}
        </View>
      </View>
    </Animated.View>
  );
}

/** The draft board: search, shared segmented position + sort strips and fixed-grid rows (free agents only). */
export function SimDraftBoard({
  gameId,
  positions,
  onOpen,
  actions,
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
      <SegmentedTabBar<string>
        scrollable
        options={[{ key: '', label: 'All' }, ...positions.map((p) => ({ key: p.value as string, label: p.label }))]}
        active={filter.pos}
        onChange={(key) => dispatch({ type: 'pos', value: key as SimPosFilter | '' })}
      />
      <View style={common.tight}>
        <AppText style={common.muted}>Sort by</AppText>
        <SegmentedTabBar<string> options={SORTS.map((o) => ({ key: o.key as string, label: o.label }))} active={filter.sort} onChange={(key) => dispatch({ type: 'sort', value: key as SimPlayerSort })} />
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
          <View style={styles.headerRow} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            {['Proj', 'Value', 'ADP', 'Edge'].map((h, i) => (
              <AppText key={h} style={[styles.headerCell, { width: STAT_COLS[i] }]}>
                {h}
              </AppText>
            ))}
          </View>
          <AppText style={styles.scaleNote}>Value is the model's 0-100 scale (top player = 100). Edge: green = steal, red = reach.</AppText>
          {rows.shown.map((player) => (
            <SimDraftRow key={player.id} player={player} onOpen={onOpen} week={week} drafted={draftedIds?.includes(player.id)} actions={actions ? actions(player) : null} />
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
  const pad = spacing.sm;
  return StyleSheet.create({
    iconButton: {
      borderRadius: radii.md,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.glassInset,
    },
    row: {
      borderLeftWidth: 3,
      paddingLeft: spacing.sm,
      paddingRight: spacing.xs,
      paddingVertical: 4,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 },
    open: { flex: 1, minWidth: 0, minHeight: 44, justifyContent: 'center' },
    identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    badgeSlot: { width: BADGE_W, alignItems: 'center' },
    avatarSlot: { width: AVATAR, height: AVATAR, alignItems: 'center', justifyContent: 'center' },
    outDot: { position: 'absolute', top: 0, right: 0, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.danger, borderWidth: 2, borderColor: colors.surface },
    nameCol: { flex: 1, minWidth: 0 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6, minWidth: 0 },
    name: { flexShrink: 1, minWidth: 0, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12, lineHeight: 16, color: colors.textTertiary },
    actions: { flexShrink: 0, flexDirection: 'row', alignItems: 'center', gap: 6 },
    draftedText: { fontSize: 12, fontWeight: '800', color: colors.accent, paddingRight: 4 },
    statsRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', columnGap: 2 },
    stat: { textAlign: 'right', fontSize: 12, fontWeight: '600', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    statCell: { alignItems: 'flex-end', minHeight: 16 },
    deltaChip: { borderRadius: radii.pill, paddingHorizontal: 6 },
    deltaText: { fontSize: 11, lineHeight: 16, fontWeight: '800', fontVariant: ['tabular-nums'] },
    headerRow: { flexDirection: 'row', justifyContent: 'flex-end', columnGap: 2, paddingRight: spacing.xs, paddingTop: spacing.xs },
    headerCell: { textAlign: 'right', fontSize: 11, fontWeight: '800', textTransform: 'uppercase', color: colors.textTertiary },
    scaleNote: { fontSize: 12, color: colors.textTertiary, paddingBottom: 2 },
    showMore: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    showMoreText: { fontSize: 14, fontWeight: '800', color: colors.accent },
    searchIcon: { position: 'absolute', left: 12, top: 13, zIndex: 1 },
    searchInput: { paddingLeft: 38 },
  });
}

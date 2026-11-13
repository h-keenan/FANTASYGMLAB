import React, { useEffect, useMemo, useReducer, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
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
import { simBoardEdge, simBoardProjection, simDraftRowChips } from '../lib/simDraft';
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
  type SimPos,
} from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

const SORTS: { key: SimPlayerSort; label: string }[] = [
  { key: 'adp', label: 'ADP' },
  { key: 'projection', label: 'Proj' },
  { key: 'value', label: 'Value' },
];

const BADGE_W = 38;
const AVATAR = 32;

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/** A 40pt icon-only action button (queue / draft / reorder / remove). */
export function SimDraftIconButton({
  icon,
  label,
  onPress,
  active = false,
  disabled = false,
  primary = false,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  active?: boolean;
  disabled?: boolean;
  primary?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tint = disabled ? colors.textTertiary : primary ? colors.accent : active ? colors.accent : colors.textSecondary;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected: active }}
      style={[styles.iconButton, (active || primary) && { backgroundColor: colors.accentMuted, borderColor: colors.accent }]}
    >
      <Ionicons name={icon} size={20} color={tint} />
    </Pressable>
  );
}

/**
 * One draft-board row, built for a 390pt phone. Line 1: position badge, photo,
 * name with the NFL team chip and status chips inline, actions (40pt icon
 * buttons) right-aligned. Line 2: Proj / Value / ADP / Edge in four equal
 * columns that match the header strip above the list.
 */
export function SimDraftRow({
  player,
  onOpen,
  actions,
  onGeneratedInfo,
}: {
  player: SimGamePlayer;
  onOpen?: (player: SimGamePlayer) => void;
  actions?: ReactNode;
  /** Opens the generated-class notice; shows a small chip on simulated rookies. */
  onGeneratedInfo?: () => void;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const edge = positionColor(player.pos, isDark, colors.borderStrong);
  const chips = simDraftRowChips(player);
  const delta = simBoardEdge(player);
  const proj = simBoardProjection(player);
  const identity = (
    <View style={styles.identity}>
      <View style={styles.badgeSlot}>
        <PositionBadge position={player.pos} />
      </View>
      <View style={styles.avatarSlot}>
        <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={AVATAR} />
      </View>
      <View style={styles.nameRow}>
        <AppText style={styles.name} numberOfLines={1}>
          {player.name}
        </AppText>
        {player.team ? (
          <View style={styles.teamTag}>
            <AppText style={styles.teamTagText}>{player.team}</AppText>
          </View>
        ) : null}
        {chips.map((chip) => (
          <ToneBadge key={chip.key} label={chip.label} color={simToneColor(chip.tone, colors)} size="xs" />
        ))}
      </View>
    </View>
  );
  return (
    <View style={[styles.row, { borderLeftColor: edge, opacity: proj.discounted ? 0.62 : 1 }]} testID="draft-row">
      <View style={styles.rowTop}>
        {onOpen ? (
          <Pressable style={styles.open} onPress={() => onOpen(player)} accessibilityRole="button" accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}>
            {identity}
          </Pressable>
        ) : (
          <View style={styles.open}>{identity}</View>
        )}
        {actions ? <View style={styles.actions}>{actions}</View> : null}
      </View>
      <View style={styles.statsRow}>
        <AppText style={styles.stat} accessibilityHint={proj.discounted ? 'Per-game projection when healthy. Out or on bye this week.' : undefined}>
          {simFmtPts(proj.value)}
        </AppText>
        <AppText style={styles.stat}>{simFmtValue(player.value)}</AppText>
        <AppText style={styles.stat}>{simFmtValue(player.adp)}</AppText>
        <View style={styles.statCell}>
          {delta ? (
            <AppText
              style={[styles.deltaText, { color: simToneColor(delta.tone, colors) }]}
              accessibilityLabel={delta.tone === 'success' ? `Steal, ${Math.abs(delta.delta)} spots` : `Reach, ${Math.abs(delta.delta)} spots`}
            >
              {delta.tone === 'success' ? '▲' : '▼'} {Math.abs(delta.delta)}
            </AppText>
          ) : null}
        </View>
        {onGeneratedInfo && simPlayerIsGenerated(player) ? (
          <View style={{ marginLeft: 'auto' }}>
            <SimGeneratedChip label="Generated" onInfo={onGeneratedInfo} compact />
          </View>
        ) : null}
      </View>
    </View>
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
}: {
  gameId: string;
  positions: SimPos[];
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
        options={[{ key: '', label: 'All' }, ...positions.map((pos) => ({ key: pos as string, label: pos }))]}
        active={filter.pos}
        onChange={(key) => dispatch({ type: 'pos', value: key as SimPos | '' })}
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
            <AppText style={styles.headerCell}>Proj</AppText>
            <AppText style={styles.headerCell}>Value</AppText>
            <AppText style={styles.headerCell}>ADP</AppText>
            <AppText style={styles.headerCell}>Edge</AppText>
          </View>
          <AppText style={styles.scaleNote}>Value is the model's 0-100 scale (top player = 100). Edge: green = steal, red = reach.</AppText>
          {rows.shown.map((player) => (
            <SimDraftRow key={player.id} player={player} onOpen={onOpen} actions={actions ? actions(player) : null} />
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
      width: 40,
      height: 40,
      borderRadius: radii.md,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.borderStrong,
    },
    row: {
      borderLeftWidth: 4,
      paddingLeft: spacing.sm,
      paddingRight: spacing.xs,
      paddingBottom: 2,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.xs },
    open: { flex: 1, minWidth: 0, minHeight: 40, justifyContent: 'center' },
    identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    badgeSlot: { width: BADGE_W, alignItems: 'center' },
    avatarSlot: { width: AVATAR, height: AVATAR, alignItems: 'center', justifyContent: 'center' },
    nameRow: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 6 },
    name: { flexShrink: 1, minWidth: 0, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    teamTag: { flexShrink: 0, borderRadius: radii.pill, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong, paddingHorizontal: 6 },
    teamTagText: { fontSize: 12, fontWeight: '800', textTransform: 'uppercase', color: colors.textSecondary },
    actions: { flexShrink: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    statsRow: { flexDirection: 'row', alignItems: 'center', paddingBottom: 2 },
    stat: { flex: 1, minWidth: 0, textAlign: 'center', fontSize: 12, fontWeight: '600', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    statCell: { flex: 1, minWidth: 0, alignItems: 'center', minHeight: 16 },
    deltaText: { fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
    headerRow: { flexDirection: 'row', paddingLeft: pad + 4, paddingRight: spacing.xs, paddingTop: spacing.xs },
    headerCell: { flex: 1, minWidth: 0, textAlign: 'center', fontSize: 12, fontWeight: '800', textTransform: 'uppercase', color: colors.textTertiary },
    scaleNote: { fontSize: 12, color: colors.textTertiary, paddingBottom: 2 },
    showMore: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
    showMoreText: { fontSize: 14, fontWeight: '800', color: colors.accent },
    searchIcon: { position: 'absolute', left: 12, top: 13, zIndex: 1 },
    searchInput: { paddingLeft: 38 },
  });
}

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
import { SimPager, createSimStyles, simToneColor, useSimDebounced } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { PLAYER_SEARCH_DEBOUNCE_MS } from '../lib/leaguePlayerSearch';
import { simDraftAdpDelta, simDraftRowChips } from '../lib/simDraft';
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

const BADGE_W = 44;
const AVATAR = 40;
const STAT_W = 44;

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/** A 44pt icon-only action button (queue / draft / reorder / remove). */
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
 * One draft-board row with fixed columns: position-colored edge, a fixed badge
 * slot, a fixed avatar slot, name / meta, then Proj / Value / ADP in fixed
 * right-aligned cells so numbers line up and photos never shift the row.
 */
export function SimDraftRow({ player, pickNo, onOpen, actions }: { player: SimGamePlayer; pickNo: number; onOpen?: (player: SimGamePlayer) => void; actions?: ReactNode }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const edge = positionColor(player.pos, isDark, colors.borderStrong);
  const chips = simDraftRowChips(player);
  const delta = simDraftAdpDelta(player.adp, pickNo);
  const identity = (
    <View style={styles.identity}>
      <View style={styles.badgeSlot}>
        <PositionBadge position={player.pos} />
      </View>
      <View style={styles.avatarSlot}>
        <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={AVATAR} />
      </View>
      <View style={styles.nameCol}>
        <AppText style={styles.name} numberOfLines={1}>
          {player.name}
        </AppText>
        <View style={styles.metaRow}>
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
    </View>
  );
  return (
    <View style={[styles.row, { borderLeftColor: edge }]} testID="draft-row">
      <View style={styles.rowTop}>
        {onOpen ? (
          <Pressable
            style={styles.open}
            onPress={() => onOpen(player)}
            accessibilityRole="button"
            accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}
          >
            {identity}
          </Pressable>
        ) : (
          <View style={styles.open}>{identity}</View>
        )}
        {actions ? <View style={styles.actions}>{actions}</View> : null}
      </View>
      <View style={styles.statsRow}>
        <AppText style={styles.stat}>{simFmtPts(player.projection)}</AppText>
        <AppText style={styles.stat}>{simFmtValue(player.value)}</AppText>
        <AppText style={styles.stat}>{simFmtValue(player.adp)}</AppText>
        <View style={styles.statCell}>
          {delta ? (
            <AppText style={[styles.deltaText, { color: simToneColor(delta.tone, colors) }]}>
              {delta.tone === 'success' ? '▲' : '▼'} {delta.label.replace('-', '')}
            </AppText>
          ) : null}
        </View>
      </View>
    </View>
  );
}

/** The draft board: search, shared segmented position + sort strips and fixed-grid rows (free agents only). */
export function SimDraftBoard({
  gameId,
  positions,
  pickNo,
  onOpen,
  actions,
  refreshKey = 0,
  onItems,
}: {
  gameId: string;
  positions: SimPos[];
  pickNo: number;
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
          {items.map((player) => (
            <SimDraftRow key={player.id} player={player} pickNo={pickNo} onOpen={onOpen} actions={actions ? actions(player) : null} />
          ))}
        </View>
      )}
      <SimPager page={filter.page} pages={simPageCount(total, SIM_PAGE_SIZE)} onPage={(page) => dispatch({ type: 'page', value: page })} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  const indent = 4 + spacing.sm + BADGE_W + spacing.sm + AVATAR + spacing.sm;
  return StyleSheet.create({
    iconButton: {
      width: 44,
      height: 44,
      borderRadius: radii.md,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.borderStrong,
    },
    row: {
      borderLeftWidth: 4,
      paddingLeft: spacing.sm,
      paddingVertical: spacing.sm,
      gap: spacing.xs,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    open: { flex: 1, minWidth: 0, minHeight: 44, justifyContent: 'center' },
    identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    badgeSlot: { width: BADGE_W, alignItems: 'center' },
    avatarSlot: { width: AVATAR, height: AVATAR, alignItems: 'center', justifyContent: 'center' },
    nameCol: { flex: 1, minWidth: 0, gap: 2 },
    name: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minHeight: 18, flexWrap: 'wrap' },
    teamTag: { borderRadius: radii.pill, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong, paddingHorizontal: 6 },
    teamTagText: { fontSize: 12, fontWeight: '800', color: colors.textSecondary },
    actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    statsRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingLeft: indent - 4 - spacing.sm },
    stat: { width: STAT_W, textAlign: 'right', fontSize: 13, fontWeight: '700', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    statCell: { width: STAT_W, alignItems: 'flex-end', minHeight: 16 },
    deltaText: { fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
    headerRow: { flexDirection: 'row', gap: spacing.sm, paddingLeft: indent, paddingTop: spacing.xs },
    headerCell: { width: STAT_W, textAlign: 'right', fontSize: 12, fontWeight: '800', textTransform: 'uppercase', color: colors.textTertiary },
    searchIcon: { position: 'absolute', left: 12, top: 13, zIndex: 1 },
    searchInput: { paddingLeft: 38 },
  });
}

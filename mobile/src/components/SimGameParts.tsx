import React, { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Animated, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import PlayerListRow from './PlayerListRow';
import AppText from './AppText';
import PlayerName from './PlayerName';
import Button from './Button';
import Collapsible from './Collapsible';
import SimGlyph from './SimGlyph';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import SimCrest from './SimCrest';
import { SIM_GLYPH_ICONS } from './SimGlyph';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import ToneBadge from './ToneBadge';
import type { PlayerListStat, PlayerListTag } from '../lib/playerListRow';
import { simDraftMeta, simDraftRowChips, simListStats } from '../lib/simDraft';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simGamePreviewLine,
  simHeadshotId,
  simTrendText,
  simPlayerInitials,
  simPlayerSubline,
  simSlotRepeatsPosition,
  type SimGlyphName,
  type SimSlot,
  type SimPlayerRef,
  type SimGame,
  type SimGameEnvelope,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
} from '../lib/simGame';
import { simSeeAllLabel } from '../lib/simLayout';
import TapForWhy from './TapForWhy';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

/** Semantic theme color for a presentation tone (never a raw hex). */
export function simToneColor(tone: SimGameTone, colors: ThemeColors): string {
  switch (tone) {
    case 'success':
      return colors.success;
    case 'warning':
      return colors.warning;
    case 'danger':
      return colors.danger;
    case 'accent':
      return colors.accent;
    default:
      return colors.textSecondary;
  }
}

/** What every game sub-screen needs from the controller (same shape as web). */
export interface SimCtx {
  gameId: string;
  game: SimGame;
  preview: SimGamePreview | null;
  call: <T extends SimGameEnvelope>(fn: () => Promise<T>) => Promise<T | null>;
  setGame: (game: SimGame) => void;
  reloadGame: () => Promise<void>;
  notify: (message: string, tone?: SimGameTone) => void;
  /** Bumped after any change that other panels should refetch for. */
  tick: number;
  bump: () => void;
  openPlayer: (player: SimGamePlayer) => void;
  /** Open any team's scouting sheet (roster, record, strengths and needs). */
  openTeam: (teamId: string) => void;
}

/** Shared status pill tinted from a presentation tone. */
export function SimToneBadge({ label, tone }: { label: string; tone: SimGameTone }) {
  const { colors } = useThemeMode();
  return <ToneBadge label={label} color={simToneColor(tone, colors)} size="xs" />;
}

/** Debounce a changing value (search boxes). */
export function useSimDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

/** Tracks the OS reduce-motion setting. Animations are skipped when true. */
export function useReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (!cancelled) setReduce(Boolean(value));
      })
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener?.('reduceMotionChanged', (value) => setReduce(Boolean(value)));
    return () => {
      cancelled = true;
      sub?.remove?.();
    };
  }, []);
  return reduce;
}

/**
 * Short, purposeful entrance for a result that just landed (recap score,
 * verdict, grade): fade plus a slight scale. Opacity/transform only; skipped
 * entirely under reduced motion. Mirrors web's `.enter-pop`.
 */
export function SimPopIn({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const reduce = useReducedMotion();
  const progress = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduce) {
      progress.setValue(1);
      return;
    }
    Animated.timing(progress, { toValue: 1, duration: 260, useNativeDriver: true }).start();
  }, [progress, reduce]);
  return (
    <Animated.View
      style={[
        style,
        {
          opacity: progress,
          transform: [{ scale: progress.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

/** Small uppercase label used over card groups. */
export function SimKicker({ children }: { children: ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return <AppText style={styles.kicker}>{children}</AppText>;
}

/** A label over a value: the one small stat used in every game screen. */
export function SimStat({ label, value, tone = 'muted' }: { label: string; value: ReactNode; tone?: SimGameTone }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.stat}>
      <AppText style={styles.statLabel}>{label}</AppText>
      <AppText style={[styles.statValue, tone !== 'muted' && { color: simToneColor(tone, colors) }]}>{value}</AppText>
    </View>
  );
}

/**
 * A trade/market value (the 0-100 number AI teams use in trades) with its real name and a tap-for-why
 * explainer. Never labeled plain "Value" or "VAL": the player's Overall is a different number.
 */
export function SimTradeValue({ value }: { value: number | null | undefined }) {
  if (value == null || Number.isNaN(value)) return null;
  const rounded = Math.round(value);
  return (
    <TapForWhy metric="trade_value" spoken={`Trade value ${rounded}`}>
      <SimStat label="Trade value" value={rounded} />
    </TapForWhy>
  );
}

/**
 * The one identity block every game surface uses for a player, whether it is
 * a full list row or a mention inside a card (injury, MVP, waiver result,
 * feed move, draft pick, lineup alert): the shared Sleeper headshot with an
 * initials fallback, name, position badge, team subline and the Out chip.
 * `size` picks the avatar (40 in list rows, 32 inside cards); the box is
 * fixed, so a photo that fails to load never shifts the row.
 */
export function SimPlayerChip({
  player,
  size = 32,
  muted = false,
  extra,
  hidePosition = false,
  onOpen,
  quick = false,
}: {
  player: SimPlayerRef;
  size?: number;
  muted?: boolean;
  extra?: ReactNode;
  /** Drop the position chip when the row's slot label already says it. */
  hidePosition?: boolean;
  /** Make the chip itself tappable with this handler (it must not already sit inside a Pressable). */
  onOpen?: (player: SimGamePlayer) => void;
  /** Make the chip tappable with the shared default: the game's player detail (the shared Player Quick View fed by the sim row). */
  quick?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const openSheet = useContext(SimOpenPlayerContext);
  const handler = onOpen ?? (quick ? openSheet : null);
  const body = (
    <View style={[styles.identity, muted && styles.muted]}>
      <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={size} />
      <View style={styles.identityText}>
        <PlayerName name={player.name} style={styles.playerName} />
        <View style={styles.sublineRow}>
          {hidePosition ? null : <PositionBadge position={player.pos} />}
          <AppText style={styles.subline} numberOfLines={1}>
            {simPlayerSubline(player)}
          </AppText>
          {player.status === 'out' ? <ToneBadge label="Out" color={colors.danger} size="xs" /> : null}
        </View>
        {extra ? <View style={styles.extra}>{extra}</View> : null}
      </View>
    </View>
  );
  if (!handler) return body;
  return (
    <Pressable onPress={() => handler(player as SimGamePlayer)} accessibilityRole="button" accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}>
      {body}
    </Pressable>
  );
}

/**
 * One player row for every game list (board, roster, waivers, trades,
 * search): the shared avatar and position badge, name, subline, with a
 * trailing slot. Sim players are not real-league players, so there is no
 * quick view; the identity block is one tap target that opens the game's own
 * player sheet.
 */
export function SimPlayerLine({
  player,
  trailing,
  onOpen,
  selected = false,
  extra,
  hidePosition = false,
  tags,
  stats,
  week = null,
}: {
  player: SimGamePlayer;
  trailing?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  /** Kept for callers that dimmed bench rows; a list row is never dimmed. */
  muted?: boolean;
  selected?: boolean;
  extra?: ReactNode;
  hidePosition?: boolean;
  tags?: PlayerListTag[];
  /** Labeled stat pills (PROJ / VAL ...); see simListStats. */
  stats?: PlayerListStat[];
  /** Current game week, to flag a bye that is close. Omit when unknown (the bye still shows). */
  week?: number | null;
}) {
  const [chip] = simDraftRowChips(player);
  return (
    <PlayerListRow
      testID="sim-player-line"
      name={player.name}
      position={hidePosition ? null : player.pos}
      headshotId={simHeadshotId(player)}
      fallbackLabel={simPlayerInitials(player)}
      meta={simDraftMeta(player, week)}
      chip={chip ? { label: chip.label, tone: chip.tone } : null}
      hurt={player.status === 'out'}
      tags={tags}
      stats={stats}
      alignColumns={stats !== undefined}
      extra={extra}
      actions={trailing}
      selected={selected}
      onOpen={onOpen ? () => onOpen(player) : undefined}
      openLabel={`${player.name}, ${player.pos}. Open player details`}
    />
  );
}

/**
 * THE roster row (lineup starters, bench, IR, taxi): one component, one info set. Age, bye, injury chip,
 * labeled PROJ and OVR, tags and tap-to-open all come from SimPlayerLine + simListStats, so a starter shows
 * exactly what a bench player shows. `slot` adds the leading slot-label column (QB, RB1, FLEX ...); a
 * flex-type slot also keeps the player's own position pill, since the slot label no longer says it.
 */
export function SimRosterLine({
  player,
  slot,
  trailing,
  onOpen,
  extra,
  week = null,
}: {
  player: SimGamePlayer;
  slot?: { slot: SimSlot; label: string };
  trailing?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  extra?: ReactNode;
  week?: number | null;
}) {
  const line = (
    <SimPlayerLine
      player={player}
      week={week}
      stats={simListStats(player, { adp: false })}
      hidePosition={slot ? simSlotRepeatsPosition(slot.slot, player.pos) : false}
      extra={extra}
      trailing={trailing}
      onOpen={onOpen}
    />
  );
  if (!slot) return line;
  return (
    <View testID="lineup-row" style={{ flexDirection: 'row', alignItems: 'stretch' }}>
      <View style={{ width: 52, alignItems: 'center', justifyContent: 'center' }}>
        <PositionBadge position={slot.slot} label={slot.label} />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>{line}</View>
    </View>
  );
}

/**
 * The shared bottom-sheet shell (SheetModal + SwipeDismissCard + scroll) every
 * other detail sheet uses, with a titled close button.
 */
export function SimSheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={`Close ${title}`}>
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose} testID="sim-sheet">
          <SheetScrollView contentContainerStyle={styles.sheetContent} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            <View style={styles.sheetTop}>
              <AppText style={styles.sheetTitle} numberOfLines={2}>
                {title}
              </AppText>
              <Pressable onPress={onClose} hitSlop={10} style={styles.closeButton} accessibilityRole="button" accessibilityLabel={`Close ${title}`}>
                <Ionicons name="close" size={18} color={colors.textSecondary} />
              </Pressable>
            </View>
            {children}
          </SheetScrollView>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

/** The free-preview strip over a game; nothing for Pro. */
export function SimPreviewBanner({ preview }: { preview: SimGamePreview | null | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const line = simGamePreviewLine(preview);
  if (!line) return null;
  return (
    <AccentCard accent={colors.premium} compact>
      <View style={styles.previewRow}>
        <ToneBadge label="Free preview" color={colors.premium} size="xs" />
        <AppText style={styles.previewText} testID="sim-preview-line">
          {line}
        </AppText>
      </View>
    </AccentCard>
  );
}

const NOTICE_ICON: Record<SimGameTone, React.ComponentProps<typeof Ionicons>['name']> = {
  success: 'trending-up',
  danger: 'medkit-outline',
  warning: 'clipboard-outline',
  accent: 'stats-chart-outline',
  muted: 'stats-chart-outline',
};

/** A transient or blocking one-line message inside a game. */
export function SimNotice({ message, tone = 'warning', onDismiss }: { message: string; tone?: SimGameTone; onDismiss?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!message) return null;
  return (
    <AccentCard accent={simToneColor(tone, colors)} compact>
      <View style={styles.noticeRow} accessibilityRole={tone === 'danger' ? 'alert' : undefined} accessibilityLiveRegion="polite">
        <Ionicons name={NOTICE_ICON[tone]} size={18} color={simToneColor(tone, colors)} style={styles.noticeIcon} />
        <AppText style={styles.noticeText}>{message}</AppText>
        {onDismiss ? (
          <Pressable onPress={onDismiss} hitSlop={10} accessibilityRole="button" accessibilityLabel="Dismiss message">
            <AppText style={styles.noticeDismiss}>Dismiss</AppText>
          </Pressable>
        ) : null}
      </View>
    </AccentCard>
  );
}

/** "You give" / "You get" label: fixed semantic color (red out, green in) with a small swap glyph. */
export function SimSideLabel({ side }: { side: 'give' | 'get' }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const color = simToneColor(side === 'give' ? 'danger' : 'success', colors);
  return (
    <View style={styles.sideLabel}>
      <Ionicons name="swap-horizontal" size={14} color={color} />
      <AppText style={[styles.sideLabelText, { color }]}>{side === 'give' ? 'You give' : 'You get'}</AppText>
    </View>
  );
}

/** Previous / next page controls. */
export function SimPager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (pages <= 1) return null;
  return (
    <View style={styles.pager}>
      <Button label="Previous" variant="secondary" size="sm" disabled={page <= 1} onPress={() => onPage(page - 1)} />
      <AppText style={styles.pagerText}>
        Page {page} of {pages}
      </AppText>
      <Button label="Next" variant="secondary" size="sm" disabled={page >= pages} onPress={() => onPage(page + 1)} />
    </View>
  );
}

/** Styles shared by the other game components (one place so rows match). */
export function createSimStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md },
    tight: { gap: spacing.xs },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    wrapRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    grow: { flex: 1, minWidth: 0 },
    body: { fontSize: 15, lineHeight: 21, color: colors.textPrimary },
    bodyStrong: { fontSize: 15, lineHeight: 21, fontWeight: '700', color: colors.textPrimary },
    small: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
    muted: { fontSize: 13, lineHeight: 18, color: colors.textTertiary },
    title: { fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    big: { fontSize: 34, fontWeight: '800', color: colors.textPrimary },
    center: { textAlign: 'center' },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    slotCol: { width: 54, alignItems: 'flex-start' },
  });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    stat: { alignItems: 'flex-end' },
    statLabel: { fontSize: 12, color: colors.textTertiary },
    statValue: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    muted: { opacity: 0.7 },
    identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flex: 1, minWidth: 0 },
    identityText: { flex: 1, minWidth: 0, gap: 2 },
    playerName: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    sublineRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.xs },
    subline: { fontSize: 13, color: colors.textTertiary, flexShrink: 1 },
    extra: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    line: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: spacing.sm,
      paddingVertical: spacing.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    lineSelected: { backgroundColor: colors.accentMuted },
    lineOpen: { flex: 1, minWidth: 200, minHeight: 44, justifyContent: 'center' },
    trailing: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginLeft: 'auto' },
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      maxHeight: '92%',
    },
    sheetContent: { padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
    sheetTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm, minHeight: 28 },
    sheetTitle: { flex: 1, fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    closeButton: {
      width: 28,
      height: 28,
      borderRadius: radii.pill,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
    },
    previewRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    previewText: { flex: 1, minWidth: 0, fontSize: 13, color: colors.textSecondary },
    noticeIcon: { width: 18, marginTop: 1 },
    sideLabel: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    sideLabelText: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase' },
    noticeRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    noticeText: { flex: 1, minWidth: 0, fontSize: 14.5, lineHeight: 20, color: colors.textPrimary },
    noticeDismiss: { fontSize: 13, fontWeight: '700', color: colors.accent },
    teamLink: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexShrink: 1, minWidth: 0 },
    teamLinkStacked: { alignItems: 'center', justifyContent: 'center', gap: spacing.xs, flexShrink: 1, minWidth: 0 },
    teamName: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    teamNameLight: { fontWeight: '500' },
    teamNameStacked: { textAlign: 'center' },
    mini: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minWidth: 0, flexShrink: 1 },
    miniRight: { flexDirection: 'row-reverse' },
    miniText: { flexShrink: 1, minWidth: 0, gap: 1 },
    miniName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    miniNameRight: { textAlign: 'right' },
    miniSub: { fontSize: 12, color: colors.textTertiary },
    miniPress: { minHeight: 32, justifyContent: 'center', flexShrink: 1, minWidth: 0 },
    pager: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    pagerText: { fontSize: 13, color: colors.textTertiary },
  });
}

// ---------------------------------------------------------------------------
// Color and glyph building blocks shared by every game screen (mirrors web)

/** Opens the team scouting sheet. Provided once by the game screen; a team link outside it is plain text. */
/** Opens the game's own player detail; provided once by the game screen so a chip can use it. */
export const SimOpenPlayerContext = createContext<((player: SimGamePlayer) => void) | null>(null);

export const SimTeamOpenContext = createContext<((teamId: string) => void) | null>(null);

/**
 * A team's emblem and name as one tap target that opens its scouting sheet
 * (roster, record, strengths and needs) from anywhere: standings, matchup,
 * trade partner, league feed.
 */
export function SimTeamLink({
  teamId,
  name,
  isYou = false,
  size = 24,
  suffix,
  bold = true,
  hideName = false,
  stacked = false,
}: {
  teamId: string | null | undefined;
  name: string;
  isYou?: boolean;
  size?: number;
  suffix?: ReactNode;
  bold?: boolean;
  /** Emblem only (the name is printed beside it); the tap target keeps the name for screen readers. */
  hideName?: boolean;
  /** Emblem above the name, centered (the matchup header). */
  stacked?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const open = useContext(SimTeamOpenContext);
  const body = (
    <>
      <SimCrest name={name} size={size} />
      {hideName ? null : (
        <AppText style={[styles.teamName, !bold && styles.teamNameLight, stacked && styles.teamNameStacked]} numberOfLines={2}>
          {name}
          {isYou ? ' (you)' : ''}
        </AppText>
      )}
      {suffix}
    </>
  );
  const layout = stacked ? styles.teamLinkStacked : styles.teamLink;
  if (!open || !teamId) return <View style={layout}>{body}</View>;
  return (
    <Pressable
      onPress={() => open(teamId)}
      style={[layout, { minHeight: 44 }]}
      accessibilityRole="button"
      accessibilityLabel={`${name}${isYou ? ' (you)' : ''}. Open team`}
    >
      {body}
    </Pressable>
  );
}

/** Section title with a tinted glyph, on the shared SectionHeading. */
export function SimSectionTitle({
  glyph,
  tone = 'accent',
  title,
  caption,
  right,
}: {
  glyph: SimGlyphName;
  tone?: SimGameTone;
  title: string;
  caption?: string | null;
  right?: ReactNode;
}) {
  const { colors } = useThemeMode();
  // SectionHeading takes an Ionicons name; the glyph map keeps web and app on the same names.
  return <SectionHeading title={title} icon={SIM_GLYPH_ICONS[glyph]} iconColor={simToneColor(tone, colors)} caption={caption} right={right} />;
}

/**
 * A summary-first card: the shared Collapsible with a tinted glyph title and
 * an always-visible summary. Open by default on wide screens and closed on
 * phones unless `openOnPhone` (mirrors web-next's SimFold).
 */
export function SimFold({ id, glyph, tone = 'accent', title, summary, openOnPhone = false, children, testID }: { id: string; glyph: SimGlyphName; tone?: SimGameTone; title: string; summary?: ReactNode; openOnPhone?: boolean; children: ReactNode; testID?: string }) {
  const { colors } = useThemeMode();
  const color = simToneColor(tone, colors);
  return (
    <Collapsible
      id={id}
      testID={testID}
      accent={color}
      defaultOpen={openOnPhone}
      title={
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
          <SimGlyph name={glyph} color={color} size={16} />
          <AppText style={{ fontSize: 14, fontWeight: '800', textTransform: 'uppercase', color: colors.textPrimary }}>{title}</AppText>
        </View>
      }
      summary={summary}
    >
      {children}
    </Collapsible>
  );
}

/** "See all (n more)" toggle under a previewed list. */
export function SimSeeAll({ hidden, expanded, onToggle, noun }: { hidden: number; expanded: boolean; onToggle: () => void; noun?: string }) {
  const { colors } = useThemeMode();
  if (hidden <= 0 && !expanded) return null;
  return (
    <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded }} style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}>
      <AppText style={{ fontSize: 13, fontWeight: '800', color: colors.accent }}>{simSeeAllLabel(hidden, expanded, noun)}</AppText>
    </Pressable>
  );
}

/** A 40pt icon-only control for dense rows (queue, draft, change). The label is the accessible name. */
export function SimIconButton({ label, onPress, pressed, primary = false, disabled = false, glyph }: { label: string; onPress: () => void; pressed?: boolean; primary?: boolean; disabled?: boolean; glyph: SimGlyphName }) {
  const { colors } = useThemeMode();
  const on = primary || pressed;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: pressed, disabled }}
      style={{
        width: 44,
        height: 44,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.md,
        borderWidth: 1,
        borderColor: on ? colors.accent : colors.borderStrong ?? colors.border,
        backgroundColor: primary ? colors.accent : pressed ? colors.accentSoft ?? 'transparent' : 'transparent',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <SimGlyph name={glyph} color={primary ? colors.onAccent ?? colors.background : on ? colors.accent : colors.textSecondary} size={16} />
    </Pressable>
  );
}

/** Green up / red down text for a points change. */
export function SimTrend({ delta, suffix = '' }: { delta: number | null | undefined; suffix?: string }) {
  const { colors } = useThemeMode();
  const t = simTrendText(delta);
  return (
    <AppText style={{ fontSize: 13, fontWeight: '800', color: simToneColor(t.tone, colors) }} testID="sim-trend">
      {t.arrow ? `${t.arrow} ` : ''}
      {t.text}
      {suffix}
    </AppText>
  );
}

/** A compact photo + name + status chip for dense two-column surfaces (matchup, cover lists). */
export function SimMiniPlayer({
  player,
  align = 'left',
  onOpen,
  size = 28,
}: {
  /** @deprecated Names never wrap: they shorten to "F. Lastname" when tight (PlayerName). */
  wrap?: boolean;
  player: SimGamePlayer;
  align?: 'left' | 'right';
  onOpen?: (player: SimGamePlayer) => void;
  size?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const hurt = player.status === 'out';
  const bye = player.status === 'bye';
  const body = (
    <View style={[styles.mini, align === 'right' && styles.miniRight]}>
      <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={size} />
      <View style={styles.miniText}>
        <PlayerName name={player.name} style={[styles.miniName, align === 'right' && styles.miniNameRight, (hurt || bye) && { color: colors.textTertiary }, hurt && { textDecorationLine: 'line-through' }]} />
        {hurt ? (
          <ToneBadge label="Out" color={colors.danger} size="xs" />
        ) : bye ? (
          <ToneBadge label="Bye" color={colors.warning} size="xs" />
        ) : (
          <AppText style={[styles.miniSub, align === 'right' && styles.miniNameRight]} numberOfLines={1}>
            {player.team ?? 'FA'}
          </AppText>
        )}
      </View>
    </View>
  );
  if (!onOpen) return body;
  return (
    <Pressable onPress={() => onOpen(player)} accessibilityRole="button" accessibilityLabel={`${player.name}, ${player.pos}. Open player details`} style={styles.miniPress}>
      {body}
    </Pressable>
  );
}

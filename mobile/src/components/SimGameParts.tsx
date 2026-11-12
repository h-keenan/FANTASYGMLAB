import React, { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Animated, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simGamePreviewLine,
  simPlayerSubline,
  type SimGame,
  type SimGameEnvelope,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
} from '../lib/simGame';
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
  muted = false,
  selected = false,
  extra,
}: {
  player: SimGamePlayer;
  trailing?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  muted?: boolean;
  selected?: boolean;
  extra?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const out = player.status === 'out';
  const identity = (
    <View style={[styles.identity, muted && styles.muted]}>
      <PlayerAvatar playerId={player.id} size={40} />
      <View style={styles.identityText}>
        <AppText style={styles.playerName} numberOfLines={2}>
          {player.name}
        </AppText>
        <View style={styles.sublineRow}>
          <PositionBadge position={player.pos} />
          <AppText style={styles.subline} numberOfLines={1}>
            {simPlayerSubline(player)}
          </AppText>
          {out ? <ToneBadge label="Out" color={colors.danger} size="xs" /> : null}
        </View>
        {extra ? <View style={styles.extra}>{extra}</View> : null}
      </View>
    </View>
  );
  return (
    <View style={[styles.line, selected && styles.lineSelected]}>
      {onOpen ? (
        <Pressable
          style={styles.lineOpen}
          onPress={() => onOpen(player)}
          accessibilityRole="button"
          accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}
        >
          {identity}
        </Pressable>
      ) : (
        <View style={styles.lineOpen}>{identity}</View>
      )}
      {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
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

/** A transient or blocking one-line message inside a game. */
export function SimNotice({ message, tone = 'warning', onDismiss }: { message: string; tone?: SimGameTone; onDismiss?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!message) return null;
  return (
    <AccentCard accent={simToneColor(tone, colors)} compact>
      <View style={styles.noticeRow} accessibilityRole={tone === 'danger' ? 'alert' : undefined} accessibilityLiveRegion="polite">
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
    noticeRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    noticeText: { flex: 1, minWidth: 0, fontSize: 14.5, lineHeight: 20, color: colors.textPrimary },
    noticeDismiss: { fontSize: 13, fontWeight: '700', color: colors.accent },
    pager: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    pagerText: { fontSize: 13, color: colors.textTertiary },
  });
}

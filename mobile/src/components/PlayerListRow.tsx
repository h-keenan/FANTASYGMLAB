import React, { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { AccessibilityInfo, Animated, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import OvrGauge from './OvrGauge';
import PlayerAvatar from './PlayerAvatar';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import TapForWhy from './TapForWhy';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ChipTone } from '../lib/playerCard';
import type { WhyMetricId } from '../lib/tapForWhyContent';
import {
  PLAYER_LIST_DENSITY,
  PLAYER_LIST_LONG_NAME,
  limitPlayerListTags,
  orderPlayerListStats,
  type PlayerListDensity,
  type PlayerListMetaPart,
  type PlayerListStat,
  type PlayerListTag,
} from '../lib/playerListRow';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

/**
 * THE player-list row (native twin of web-next/src/components/PlayerListRow.tsx):
 * the `list` variant of the player card system, docs/player-card.md. Line 1:
 * position badge, photo, name, one status chip only when it matters. Line 2:
 * muted TEAM · Age · Bye. Line 3: page tags (2 + "+N") and LABELED stat pills
 * (PROJ / OVR / TRADE VALUE / ADP / EDGE; OVR is the shared overall gauge) in fixed slots. Actions slot and tap-to-open. An
 * injured row is never dimmed.
 */

export interface PlayerListRowProps {
  name: string;
  position: string | null;
  headshotId?: string | null;
  fallbackLabel?: string;
  meta?: PlayerListMetaPart[];
  chip?: { label: string; tone: ChipTone } | null;
  hurt?: boolean;
  stats?: PlayerListStat[];
  tags?: PlayerListTag[];
  extra?: ReactNode;
  /** Small inline controls at the end of the chips line (e.g. a Queue toggle), so the trailing slot stays ONE action. */
  chipsExtra?: ReactNode;
  actions?: ReactNode;
  onOpen?: () => void;
  openLabel?: string;
  density?: PlayerListDensity;
  /** Optimistic: just picked / added; fades and slides out. */
  done?: boolean;
  doneLabel?: string;
  onSimInfo?: () => void;
  testID?: string;
  selected?: boolean;
  /** Every row of this list shows the same stats: anchor the stat block left at a fixed width so columns line up even when only some rows have an EDGE. */
  alignColumns?: boolean;
}

function toneColor(tone: ChipTone | undefined, colors: ThemeColors, fallback: string): string {
  switch (tone) {
    case 'success':
      return colors.success;
    case 'danger':
      return colors.danger;
    case 'warning':
      return colors.warning;
    case 'accent':
      return colors.accent;
    case 'muted':
      return colors.textTertiary;
    default:
      return fallback;
  }
}

export default function PlayerListRow({
  name,
  position,
  headshotId,
  fallbackLabel,
  meta = [],
  chip,
  hurt = false,
  stats = [],
  tags = [],
  extra,
  chipsExtra,
  actions,
  onOpen,
  openLabel,
  density = 'comfortable',
  done = false,
  doneLabel = 'Drafted ✓',
  onSimInfo,
  testID = 'player-list-row',
  selected = false,
}: PlayerListRowProps) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const dims = PLAYER_LIST_DENSITY[density];
  const edge = positionColor(position ?? '', isDark, colors.borderStrong);
  const slots = orderPlayerListStats(stats);
  const { shown, extra: moreTags } = limitPlayerListTags(tags);
  const slide = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!done) {
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
  }, [done, slide]);

  const identity = (
    <View style={styles.identity}>
      <View style={styles.badgeSlot}>
        <PositionBadge position={position ?? ''} />
      </View>
      <View style={{ width: dims.avatar, height: dims.avatar, alignItems: 'center', justifyContent: 'center' }}>
        <PlayerAvatar playerId={headshotId ?? null} fallbackLabel={fallbackLabel ?? name.slice(0, 2)} size={dims.avatar} />
        {hurt ? <View style={styles.hurtDot} /> : null}
      </View>
      <View style={styles.nameCol}>
        <View style={styles.nameRow}>
          <PlayerName name={name} style={[styles.name, name.length > PLAYER_LIST_LONG_NAME && { fontSize: 13 }]} />
          {chip ? <ToneBadge label={chip.label.toUpperCase()} color={toneColor(chip.tone, colors, colors.textSecondary)} size="xs" /> : null}
        </View>
        {meta.length > 0 ? (
          <AppText style={styles.meta} testID="list-meta">
            {meta.map((part, i) => (
              <AppText key={part.key} style={[styles.meta, part.tone && { color: toneColor(part.tone, colors, colors.textTertiary) }, part.tone === 'warning' && { fontWeight: '700' }]}>
                {i > 0 ? ' · ' : ''}
                {part.text}
              </AppText>
            ))}
          </AppText>
        ) : null}
        {extra}
      </View>
    </View>
  );

  return (
    <Animated.View
      style={[
        styles.row,
        { borderLeftColor: edge },
        selected && { backgroundColor: colors.accentMuted },
        done && { opacity: slide.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ translateX: slide.interpolate({ inputRange: [0, 1], outputRange: [0, 24] }) }] },
      ]}
      pointerEvents={done ? 'none' : 'auto'}
      testID={testID}
    >
      <View style={styles.rowTop}>
        {onOpen ? (
          <Pressable style={[styles.open, { minHeight: dims.minHeight }]} onPress={onOpen} accessibilityRole="button" accessibilityLabel={openLabel ?? `${name}${position ? `, ${position}` : ''}. Open player details`}>
            {identity}
          </Pressable>
        ) : (
          <View style={[styles.open, { minHeight: dims.minHeight }]}>{identity}</View>
        )}
        {onSimInfo && !done ? (
          <Pressable onPress={onSimInfo} accessibilityRole="button" accessibilityLabel="About simulated players" style={styles.simInfo} hitSlop={8}>
            <Ionicons name="information-circle-outline" size={18} color={colors.accent} />
          </Pressable>
        ) : null}
        {done ? (
          <AppText style={styles.doneText} accessibilityLiveRegion="polite">
            {doneLabel}
          </AppText>
        ) : actions ? (
          <View style={styles.actions}>{actions}</View>
        ) : null}
      </View>
      {slots.length > 0 || shown.length > 0 || chipsExtra ? (
        <View style={[styles.chips, { paddingLeft: 34 + dims.avatar + spacing.sm * 2 }]} testID="list-chips">
          <View style={styles.chipGroup} testID="list-stats">
            {slots.map((stat) =>
              stat ? (
                stat.rating != null ? (
                  // The player's Overall is the shared OVR gauge (same ring, thresholds and colors as the Quick View hero).
                  <TapForWhy key={stat.key} metric="ovr" spoken={`Overall ${stat.rating}`}>
                    <View style={styles.gaugeStat}>
                      <AppText style={styles.pillLabel}>{stat.label}</AppText>
                      <OvrGauge rating={stat.rating} size="xs" />
                    </View>
                  </TapForWhy>
                ) : stat.why ? (
                  <TapForWhy key={stat.key} metric={stat.why as WhyMetricId} spoken={`${stat.label} ${stat.value}`}>
                    <View style={styles.pill}>
                      <AppText style={styles.pillLabel}>{stat.label}</AppText>
                      <AppText style={styles.pillValue}>{stat.value}</AppText>
                    </View>
                  </TapForWhy>
                ) : (
                  <View key={stat.key} style={styles.pill}>
                    <AppText style={styles.pillLabel}>{stat.label}</AppText>
                    <AppText style={[styles.pillValue, stat.tone && { color: toneColor(stat.tone, colors, colors.textPrimary) }]}>{stat.value}</AppText>
                  </View>
                )
              ) : null,
            )}
          </View>
          <View style={styles.chipGroup} testID="list-tags">
            {shown.map((tag) => (
              <ToneBadge key={tag.key} label={tag.label} color={toneColor(tag.tone, colors, colors.textSecondary)} size="xs" shrink />
            ))}
            {moreTags > 0 ? <AppText style={styles.more}>+{moreTags}</AppText> : null}
          </View>
          {chipsExtra}
        </View>
      ) : null}
    </Animated.View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: {
      borderLeftWidth: 3,
      paddingLeft: spacing.sm,
      paddingRight: spacing.xs,
      paddingVertical: 4,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 },
    open: { flex: 1, minWidth: 0, justifyContent: 'center' },
    identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    badgeSlot: { width: 34, alignItems: 'center' },
    hurtDot: { position: 'absolute', top: 0, right: 0, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.danger, borderWidth: 2, borderColor: colors.surface },
    nameCol: { flex: 1, minWidth: 0 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6, minWidth: 0 },
    name: { flexShrink: 1, minWidth: 0, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12, lineHeight: 16, color: colors.textTertiary },
    actions: { flexShrink: 0, flexDirection: 'row', alignItems: 'center', gap: 6 },
    simInfo: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
    doneText: { fontSize: 12, fontWeight: '800', color: colors.accent, paddingRight: 4 },
    chips: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 6, rowGap: 4, paddingTop: 2, paddingBottom: 4 },
    chipGroup: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 6, rowGap: 4 },
    more: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    gaugeStat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    pill: { flexDirection: 'row', alignItems: 'baseline', gap: 4, borderRadius: radii.pill, paddingHorizontal: 6, backgroundColor: colors.glassInput },
    pillLabel: { fontSize: 12, lineHeight: 16, fontWeight: '600', color: colors.textTertiary },
    pillValue: { fontSize: 12, lineHeight: 16, fontWeight: '700', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  });
}

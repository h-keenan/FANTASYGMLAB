import React, { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import PositionBadge from './PositionBadge';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { feedAgeLabel, feedPointsLabel, groupFeedByGame, liveFeedStore, type FeedEvent } from '../lib/liveFeed';
import { radii, spacing, type ThemeColors } from '../theme';
import PlayerName from './PlayerName';

/**
 * Collapsible "Live feed": scoring events derived by diffing polled snapshots
 * while this screen is open (lib/liveFeed.ts). Latest first, grouped by NFL
 * game, no auto-scroll, "NEW" on items that arrived since the panel was last
 * closed, at most 50 kept, in memory per matchup. Times are poll times, items
 * are marked "approx." when several things merged. Twin of web-next's
 * LiveFeedPanel.
 */
export default function LiveFeedPanel({ feedKey, live }: { feedKey: string; live: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const events = useSyncExternalStore(
    liveFeedStore.subscribe,
    () => liveFeedStore.events(feedKey),
    () => liveFeedStore.events(feedKey),
  );
  const [open, setOpen] = useState(false);
  const [seenAt, setSeenAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!open) return;
    const timer = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(timer);
  }, [open]);

  if (events.length === 0 && !live) return null;
  const unseen = events.filter((event) => event.at > seenAt).length;
  const groups = groupFeedByGame(events, liveFeedStore.snapshot(feedKey));
  const toggle = () => {
    if (open) setSeenAt(Date.now());
    else setNow(Date.now());
    setOpen((value) => !value);
  };

  return (
    <AnimatedCard style={styles.card} testID="live-feed">
      <PressableScale onPress={toggle} accessibilityRole="button" accessibilityState={{ expanded: open }} style={styles.header}>
        <View style={styles.titleRow}>
          <AppText style={styles.title}>LIVE FEED</AppText>
          {live ? <ToneBadge size="xs" label="● LIVE" color={colors.successBright} /> : null}
          {!open && unseen > 0 ? <ToneBadge size="xs" label={`${unseen} new`} color={colors.accent} /> : null}
        </View>
        <AppText style={styles.toggle}>{open ? 'Hide' : `Show${events.length ? ` (${events.length})` : ''}`}</AppText>
      </PressableScale>
      {open ? (
        <View style={{ gap: spacing.md }} accessibilityLiveRegion="polite">
          {events.length === 0 ? (
            <AppText style={styles.muted}>Scoring changes appear here as they happen while this screen is open.</AppText>
          ) : (
            groups.map((game) => (
              <View key={game.key} style={{ gap: 6 }}>
                <AppText style={styles.gameHeader}>
                  {game.label}
                  {game.status ? `  ·  ${game.status}` : ''}
                </AppText>
                {game.events.map((event) => (
                  <FeedItem key={event.id} event={event} now={now} isNew={event.at > seenAt} />
                ))}
              </View>
            ))
          )}
          <AppText style={styles.muted}>
            Built from score changes between refreshes, so times are when we noticed (not the play clock) and busy drives may be combined (“approx.”).
          </AppText>
        </View>
      ) : null}
    </AnimatedCard>
  );
}

function FeedItem({ event, now, isNew }: { event: FeedEvent; now: number; isNew: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.item, { borderLeftColor: event.side === 'mine' ? colors.accent : colors.borderStrong }]}>
      <PositionBadge position={event.position} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <View style={styles.nameRow}>
          <PlayerName name={event.name} style={styles.name} />
          <AppText style={[styles.points, { color: event.points < 0 ? colors.danger : colors.successBright }]}>
            {feedPointsLabel(event.points)}
          </AppText>
        </View>
        <AppText style={styles.detail}>
          {event.detail}
          {event.approx ? ' · approx.' : ''}
        </AppText>
      </View>
      <View style={{ alignItems: 'flex-end', gap: 2 }}>
        <AppText style={styles.muted}>{feedAgeLabel(event.at, now)}</AppText>
        <AppText style={[styles.side, { color: event.side === 'mine' ? colors.accent : colors.textTertiary }]}>
          {event.side === 'mine' ? 'YOU' : 'OPP'}
        </AppText>
        {isNew ? <ToneBadge size="xs" label="NEW" color={colors.accent} /> : null}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.lg, gap: spacing.md },
    header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { fontSize: 14, fontWeight: '800', letterSpacing: 0.8, color: colors.textPrimary },
    toggle: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
    gameHeader: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    item: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      paddingVertical: 8,
      paddingHorizontal: 10,
      borderRadius: radii.md,
      borderWidth: 1,
      borderLeftWidth: 3,
      borderColor: colors.glassInputBorder,
      backgroundColor: colors.glassInput,
    },
    nameRow: { flexDirection: 'row', alignItems: 'baseline', gap: 6 },
    name: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    points: { fontSize: 14.5, fontWeight: '800', fontVariant: ['tabular-nums'] },
    detail: { fontSize: 12.5, color: colors.textSecondary },
    side: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6 },
    muted: { fontSize: 12.5, color: colors.textTertiary },
  });
}

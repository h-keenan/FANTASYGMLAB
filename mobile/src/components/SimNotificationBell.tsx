import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import { PulseOnIncrease } from './Motion';
import { Sheet } from './Sheet';
import SimGlyph from './SimGlyph';
import type { SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import type { SimGlyphName } from '../lib/simGame';
import {
  simNotifBadge,
  simNotifCursorKey,
  simNotifGroups,
  simNotifKey,
  simNotifMarkAllRead,
  simNotifParseCursor,
  simNotifTargetTab,
  simNotifTime,
  simNotifUnread,
  type SimNotifTab,
  type SimNotification,
} from '../lib/simNotifications';
import { spacing } from '../theme';

/**
 * The bell's data (twin of web-next's useSimNotifications): ONE request, refetched only when the game changed
 * (simNotifKey), never on a timer; the read cursor is a number in AsyncStorage per game.
 */
export function useSimNotifications(ctx: SimCtx) {
  const { gameId, game } = ctx;
  const [items, setItems] = useState<SimNotification[]>([]);
  const [latest, setLatest] = useState(0);
  const [cursor, setCursor] = useState(0);
  const key = simNotifKey(game, ctx.tick);

  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(simNotifCursorKey(gameId))
      .then((raw) => {
        if (active) setCursor(simNotifParseCursor(raw));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [gameId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let since = 0;
      try {
        since = simNotifParseCursor(await AsyncStorage.getItem(simNotifCursorKey(gameId)));
      } catch {
        since = 0;
      }
      try {
        const body = await api.getSimNotifications(gameId, since);
        if (cancelled || body.reason) return;
        setItems(body.items ?? []);
        setLatest(body.seq ?? 0);
      } catch {
        /* the bell is a convenience: a failed fetch just keeps the last list */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gameId, key]);

  const unread = useMemo(() => simNotifUnread(items, cursor), [items, cursor]);
  const markAllRead = useCallback(() => {
    const next = simNotifMarkAllRead(cursor, latest);
    setCursor(next);
    AsyncStorage.setItem(simNotifCursorKey(gameId), String(next)).catch(() => {});
  }, [cursor, latest, gameId]);
  return { items, unread, cursor, markAllRead };
}

/** The header bell: unread badge (pulses on a new one) and the notification sheet. Web twin: components/SimNotificationBell.tsx. */
export function SimNotificationBell({ notif, onOpenTab }: { notif: ReturnType<typeof useSimNotifications>; onOpenTab: (tab: SimNotifTab) => void }) {
  const { colors } = useThemeMode();
  const { items, unread, cursor, markAllRead } = notif;
  const [open, setOpen] = useState(false);
  const [seenCursor, setSeenCursor] = useState(0);
  const groups = useMemo(() => simNotifGroups(items), [items]);
  const badge = simNotifBadge(unread);

  function openSheet() {
    setSeenCursor(cursor);
    setOpen(true);
    markAllRead();
  }

  return (
    <>
      <Pressable onPress={openSheet} accessibilityRole="button" accessibilityLabel={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'} style={styles.icon} testID="sim-bell">
        <Ionicons name="notifications-outline" size={20} color={colors.textSecondary} />
        {badge ? (
          <View style={styles.badgeWrap} testID="sim-bell-badge">
            <PulseOnIncrease value={unread}>
              <View style={[styles.badge, { backgroundColor: colors.accent }]}>
                <AppText style={[styles.badgeText, { color: colors.onAccent }]}>{badge}</AppText>
              </View>
            </PulseOnIncrease>
          </View>
        ) : null}
      </Pressable>
      <Sheet open={open} onClose={() => setOpen(false)} title="Notifications" description="What happened in your game.">
        {items.length === 0 ? (
          <AppText style={{ color: colors.textTertiary, textAlign: 'center', paddingVertical: spacing.lg }}>Nothing yet. Offers, claims, injuries and recaps land here.</AppText>
        ) : (
          <View style={{ gap: spacing.md }}>
            <View style={{ alignItems: 'flex-end' }}>
              <Button size="sm" variant="ghost" label="Mark all read" disabled={unread === 0 && cursor >= seenCursor} onPress={markAllRead} />
            </View>
            {groups.map((group) => (
              <View key={group.week} accessibilityLabel={group.label}>
                <AppText style={[styles.groupLabel, { color: colors.textTertiary }]}>{group.label.toUpperCase()}</AppText>
                {group.items.map((item) => {
                  const isNew = item.seq > seenCursor;
                  return (
                    <Pressable
                      key={item.id}
                      onPress={() => {
                        setOpen(false);
                        onOpenTab(simNotifTargetTab(item.target));
                      }}
                      accessibilityRole="button"
                      accessibilityLabel={`${item.headline}. ${simNotifTime(item)}`}
                      style={[styles.row, { borderTopColor: colors.border }]}
                    >
                      <View style={[styles.iconWrap, { backgroundColor: colors.backgroundElevated ?? 'transparent' }]}>
                        <SimGlyph name={item.icon as SimGlyphName} color={colors.accent} size={18} />
                      </View>
                      <AppText style={[styles.headline, { color: colors.textPrimary, fontWeight: isNew ? '800' : '600' }]}>{item.headline}</AppText>
                      <AppText style={{ color: colors.textTertiary, fontSize: 12 }}>{simNotifTime(item)}</AppText>
                      {isNew ? <View style={[styles.dot, { backgroundColor: colors.accent }]} accessibilityLabel="New" /> : null}
                    </Pressable>
                  );
                })}
              </View>
            ))}
          </View>
        )}
      </Sheet>
    </>
  );
}

const styles = StyleSheet.create({
  icon: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  badgeWrap: { position: 'absolute', top: 2, right: 0 },
  badge: { minWidth: 18, height: 18, paddingHorizontal: 5, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontSize: 12, fontWeight: '800', lineHeight: 14 },
  groupLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, paddingBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 56, borderTopWidth: StyleSheet.hairlineWidth },
  iconWrap: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  headline: { flex: 1, fontSize: 14 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});

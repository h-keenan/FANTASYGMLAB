import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Linking, RefreshControl, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api, type AlertItem } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Alerts'>;

const EVENT_BADGE_COLORS: Record<string, string> = {
  'injury/status': colors.danger,
  transaction: colors.accent,
  'role/depth chart': colors.success,
  'off-field/drama': colors.textSecondary,
};

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — Alerts needs to know which players are yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: 'Your roster in this league is empty.',
  no_player_data: "Couldn't load player data right now.",
};

function relativeTime(publishedTs: number | null): string {
  if (!publishedTs) return '';
  const seconds = Date.now() / 1000 - publishedTs;
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function AlertsScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<AlertItem[]>([]);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: `Alerts — ${leagueName}` });
  }, [leagueName, navigation]);

  const load = useCallback(async () => {
    setError(null);
    setNotReadyReason(null);
    try {
      const result = await api.getLeagueAlerts(leagueId, 12);
      if (result.reason) {
        setNotReadyReason(result.reason);
      } else {
        setItems(result.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts.');
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    void load();
  }, [load]);

  const openAndMarkRead = (item: AlertItem) => {
    if (!item.read) {
      setItems((prev) => prev.map((row) => (row.alert_key === item.alert_key ? { ...row, read: true } : row)));
      // Fire-and-forget: read state is a soft-fail nicety (see the backend's
      // "fails closed" design), never worth blocking or erroring the tap on.
      api.markAlertRead(leagueId, item.alert_key).catch(() => {});
    }
    if (item.link) void Linking.openURL(item.link);
  };

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't load alerts for this league."}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.disclaimer}>
        Recent news about players on your roster in {leagueName} — injury, role, transaction, and
        off-field signal only.
      </Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={items}
        keyExtractor={(item, index) => item.link ?? String(index)}
        contentContainerStyle={styles.listContent}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={
          !loading ? <Text style={styles.empty}>No relevant news for your roster right now.</Text> : null
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={StyleSheet.flatten([styles.card, item.read && styles.cardRead])}
            onPress={() => openAndMarkRead(item)}
          >
            <View style={styles.headerRow}>
              <View style={styles.headerLeft}>
                {!item.read ? <View style={styles.unreadDot} /> : null}
                {item.matched_player ? (
                  <View style={styles.playerBadge}>
                    <Text style={styles.playerBadgeText}>{item.matched_player}</Text>
                  </View>
                ) : null}
              </View>
              <Text style={styles.time}>{relativeTime(item.published_ts)}</Text>
            </View>
            {item.event_type ? (
              <View
                style={[
                  styles.badge,
                  { backgroundColor: EVENT_BADGE_COLORS[item.event_type] ?? colors.textSecondary },
                ]}
              >
                <Text style={styles.badgeText}>{item.event_type}</Text>
              </View>
            ) : null}
            <Text style={[styles.title, item.read && styles.titleRead]} numberOfLines={2}>
              {item.title}
            </Text>
            {item.summary ? (
              <Text style={styles.summary} numberOfLines={3}>
                {item.summary}
              </Text>
            ) : null}
            {item.speculative ? <Text style={styles.speculative}>Unconfirmed / speculative</Text> : null}
          </AnimatedCard>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  card: { padding: spacing.lg },
  cardRead: { opacity: 0.6 },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.accent,
  },
  playerBadge: {
    backgroundColor: colors.badgeBackground,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  playerBadgeText: { color: colors.badgeText, fontSize: 11, fontWeight: '700' },
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
    marginBottom: spacing.xs,
  },
  badgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  time: { fontSize: 12, color: colors.textSecondary },
  title: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginBottom: spacing.xs },
  titleRead: { fontWeight: '500' },
  summary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  speculative: {
    fontSize: 11,
    color: colors.textSecondary,
    fontStyle: 'italic',
    marginTop: spacing.xs,
  },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
});

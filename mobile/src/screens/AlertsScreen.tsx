import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Linking, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type AlertItem, type RankedPlayer, type RosterRelationship } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Alerts'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];

const EVENT_BADGE_COLORS: Record<string, string> = {
  'injury/status': colors.danger,
  transaction: colors.accent,
  'role/depth chart': colors.success,
  'off-field/drama': colors.textSecondary,
};

const EVENT_BADGE_ICONS: Record<string, IconName> = {
  'injury/status': 'medkit-outline',
  transaction: 'swap-horizontal-outline',
  'role/depth chart': 'layers-outline',
  'off-field/drama': 'alert-circle-outline',
};

const ROSTER_RELATIONSHIP_LABEL: Record<Exclude<RosterRelationship, null>, string> = {
  starter: 'Starter',
  bench: 'Bench',
  taxi: 'Taxi',
  ir: 'IR',
};

const ROSTER_RELATIONSHIP_COLOR: Record<Exclude<RosterRelationship, null>, string> = {
  starter: colors.success,
  bench: colors.textSecondary,
  taxi: colors.violet,
  ir: colors.danger,
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
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<AlertItem[]>([]);
  const [recapReadyWeek, setRecapReadyWeek] = useState<number | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Alerts', leagueName);

  const load = useCallback(async () => {
    setError(null);
    setNotReadyReason(null);
    try {
      const [result, recapResult] = await Promise.all([
        api.getLeagueAlerts(leagueId, 12),
        api.getLeagueRecap(leagueId).catch(() => null),
      ]);
      if (result.reason) {
        setNotReadyReason(result.reason);
      } else {
        setItems(result.items);
      }
      setRecapReadyWeek(recapResult?.recap && !recapResult.recap.incomplete ? recapResult.recap.week : null);
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

  const openPlayer = (item: AlertItem) => {
    if (!item.matched_player_id || !item.matched_player) return;
    const player: RankedPlayer = {
      player_id: item.matched_player_id,
      name: item.matched_player,
      position: null,
      team: null,
      age: null,
      status: null,
      injury_status: null,
      tier: null,
      score: null,
      overall_rank: null,
      position_rank: null,
      rank_unavailable_reason: null,
      opportunity_label: null,
    };
    navigation.navigate('PlayerDetail', { player, leagueId, leagueName });
  };

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <AppText style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't load alerts for this league."}
        </AppText>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <GridBackground />
      <ScreenHero title="ALERTS" subtitle={leagueName} />
      <AppText style={styles.disclaimer}>
        Recent news about players on your roster in {leagueName} — injury, role, transaction, and
        off-field signal only.
      </AppText>

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        data={items}
        keyExtractor={(item, index) => item.link ?? String(index)}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          recapReadyWeek != null ? (
            <TouchableOpacity onPress={() => navigation.navigate('Recap', { leagueId, leagueName })}>
              <AnimatedCard style={styles.recapCard}>
                <IconCircle name="newspaper-outline" color={colors.accent} size={36} style={styles.recapIconDisc} />
                <View style={styles.recapTextGroup}>
                  <AppText style={styles.recapTitle}>Week {recapReadyWeek} League Recap is ready</AppText>
                  <AppText style={styles.recapSubtitle}>Tap to see this week's storylines</AppText>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
              </AnimatedCard>
            </TouchableOpacity>
          ) : null
        }
        ListEmptyComponent={
          !loading ? (
            <EmptyState
              icon="checkmark-circle-outline"
              title="All quiet"
              subtitle="No relevant news for your roster right now."
            />
          ) : null
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
                  <TouchableOpacity
                    style={styles.playerBadge}
                    onPress={() => openPlayer(item)}
                    disabled={!item.matched_player_id}
                    hitSlop={4}
                  >
                    {item.matched_player_id ? (
                      <PlayerAvatar playerId={item.matched_player_id} size={28} style={styles.playerBadgeAvatar} />
                    ) : null}
                    <AppText style={styles.playerBadgeText}>{item.matched_player}</AppText>
                  </TouchableOpacity>
                ) : null}
                {item.roster_relationship ? (
                  <View
                    style={[
                      styles.relationshipPill,
                      { backgroundColor: `${ROSTER_RELATIONSHIP_COLOR[item.roster_relationship]}26` },
                    ]}
                  >
                    <AppText
                      style={[
                        styles.relationshipPillText,
                        { color: ROSTER_RELATIONSHIP_COLOR[item.roster_relationship] },
                      ]}
                    >
                      {ROSTER_RELATIONSHIP_LABEL[item.roster_relationship]}
                    </AppText>
                  </View>
                ) : null}
              </View>
              <AppText style={styles.time}>{relativeTime(item.published_ts)}</AppText>
            </View>
            {item.event_type ? (
              <View
                style={[
                  styles.badge,
                  { backgroundColor: EVENT_BADGE_COLORS[item.event_type] ?? colors.textSecondary },
                ]}
              >
                <Ionicons
                  name={EVENT_BADGE_ICONS[item.event_type] ?? 'information-circle-outline'}
                  size={11}
                  color="#fff"
                  style={styles.badgeIcon}
                />
                <AppText style={styles.badgeText}>{item.event_type}</AppText>
              </View>
            ) : null}
            <AppText style={[styles.title, item.read && styles.titleRead]} numberOfLines={2}>
              {item.title}
            </AppText>
            {item.summary ? (
              <AppText style={styles.summary} numberOfLines={3}>
                {item.summary}
              </AppText>
            ) : null}
            {item.speculative ? <AppText style={styles.speculative}>Unconfirmed / speculative</AppText> : null}
            {item.source ? <AppText style={styles.source}>Source: {item.source}</AppText> : null}
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
  recapCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.accentMuted,
  },
  recapIconDisc: { marginRight: spacing.sm },
  recapTextGroup: { flex: 1 },
  recapTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  recapSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
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
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.badgeBackground,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  playerBadgeAvatar: { marginRight: spacing.xs },
  playerBadgeText: { color: colors.badgeText, fontSize: 12, fontWeight: '700' },
  relationshipPill: { borderRadius: radii.pill, paddingHorizontal: spacing.xs + 2, paddingVertical: 1 },
  relationshipPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
    marginBottom: spacing.xs,
  },
  badgeIcon: { marginRight: 4 },
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
  source: {
    fontSize: 11,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
});

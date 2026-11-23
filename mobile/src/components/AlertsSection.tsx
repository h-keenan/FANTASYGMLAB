import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import { ExpandRow, ExpandRowGroup } from './ExpandRow';
import SectionHeading from './SectionHeading';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import ErrorState from './ErrorState';
import PlayerIdentityRow from './PlayerIdentityRow';
import PressableScale from './PressableScale';
import { Collapse } from './Presence';
import RecapReadyCard from './RecapReadyCard';
import { api, type AlertItem, type RankedPlayer, type RosterRelationship, type RoundupNotice } from '../lib/api';
import { alertReadSync, currentAlertReadUserId } from '../lib/alertReads';
import { toUserErrorMessage } from '../lib/errorMessages';
import { todayAlertRows, type TodayAlertLine, type TodayAlertRow } from '../lib/todayView';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

// Semantic mapping preserved from the pre-redesign screen: red = injury/risk,
// cyan = transaction/GM intelligence, green = role upside, gray = everything
// else. These already line up with the Magna Carta's §3 semantic system, so
// the redesign reuses them rather than inventing a new palette per type.
function eventBadgeColors(colors: ThemeColors): Record<string, string> {
  return {
    'injury/status': colors.danger,
    transaction: colors.accent,
    'role/depth chart': colors.success,
    'off-field/drama': colors.textSecondary,
  };
}

const EVENT_BADGE_ICONS: Record<string, IconName> = {
  'injury/status': 'medkit-outline',
  transaction: 'swap-horizontal-outline',
  'role/depth chart': 'layers-outline',
  'off-field/drama': 'alert-circle-outline',
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  'injury/status': 'Injury / Status',
  transaction: 'Transaction',
  'role/depth chart': 'Role / Depth Chart',
  'off-field/drama': 'Off-Field',
};

function eventTypeLabel(eventType: string | null): string {
  if (!eventType) return 'Update';
  return (
    EVENT_TYPE_LABELS[eventType] ??
    eventType
      .split('/')
      .map((part) => part.replace(/\b\w/g, (c) => c.toUpperCase()))
      .join(' / ')
  );
}

const ROSTER_RELATIONSHIP_LABEL: Record<Exclude<RosterRelationship, null>, string> = {
  starter: 'Starter',
  bench: 'Bench',
  taxi: 'Taxi',
  ir: 'IR',
};

function rosterRelationshipColor(colors: ThemeColors): Record<Exclude<RosterRelationship, null>, string> {
  return {
    starter: colors.success,
    bench: colors.textSecondary,
    taxi: colors.violet,
    ir: colors.danger,
  };
}

export const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first. Alerts needs to know which players are yours.",
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

interface AlertGroup {
  eventType: string | null;
  alerts: AlertItem[];
}

/**
 * Clusters consecutive alerts that share the same event_type into one group.
 * Keeps the feed's existing chronological order intact (only adjacent runs
 * merge), so a burst of same-type news shares one surface with dividers
 * instead of repeating an identical bordered card per item — the alert TYPE
 * is still communicated per-row via semantic color/icon, not by splitting
 * unrelated types into separate boxes (Magna Carta §12).
 */
function groupAlertsByType(items: AlertItem[]): AlertGroup[] {
  const groups: AlertGroup[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.eventType === item.event_type) {
      last.alerts.push(item);
    } else {
      groups.push({ eventType: item.event_type, alerts: [item] });
    }
  }
  return groups;
}

/**
 * Alerts on Today: news about YOUR rostered players only, as action rows (avatar, one line, ONE button: Swap / Lineup for a
 * starter, Read for a bench player). League-wide headlines never appear. "All alerts" opens the grouped roster-news feed
 * (and the watchlist). Read state syncs through lib/alertReads (server + device). `forceOpen` opens the full feed (and the
 * host scrolls here) when the route asks for focus 'alerts'. Web twin: components/DashboardAlerts.tsx.
 */
export default function AlertsSection({
  leagueId,
  leagueName,
  forceOpen = false,
  unreadReported,
  watchLines = [],
  watchBody,
}: {
  leagueId: string;
  leagueName: string;
  forceOpen?: boolean;
  /** The Dashboard's watchlist items, folded into this section: their players and headlines join the collapsed line. */
  watchLines?: TodayAlertLine[];
  /** The watchlist rows, shown at the top of the expanded section. */
  watchBody?: React.ReactNode;
  /** Lets the host (header bell, etc.) know the unread count. */
  unreadReported?: (count: number) => void;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [items, setItems] = useState<AlertItem[]>([]);
  const [roundupNotice, setRoundupNotice] = useState<RoundupNotice | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isRestoring = useIsRestoring();
  // Shares its cache entry with Dashboard/Recap/GmOrb's own recap fetches (queryKeys.recap).
  const recapQuery = useQuery({
    queryKey: queryKeys.recap(leagueId),
    queryFn: () => api.getLeagueRecap(leagueId),
    enabled: !isRestoring,
  });
  const recapReadyWeek =
    recapQuery.data?.recap && !recapQuery.data.recap.incomplete ? recapQuery.data.recap.week : null;

  const load = useCallback(async () => {
    setError(null);
    setNotReadyReason(null);
    try {
      const result = await api.getLeagueAlerts(leagueId, 12);
      if (result.reason) {
        setNotReadyReason(result.reason);
      } else {
        // `read` is the server's cross-device state (shared with the web app), overlaid with any read tapped
        // here that hasn't synced yet.
        const userId = await currentAlertReadUserId();
        setItems(await alertReadSync.reconcile(userId, leagueId, result.items));
        setRoundupNotice(result.roundup_notice ?? null);
      }
    } catch (err) {
      setError(toUserErrorMessage(err, 'Failed to load alerts.'));
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Only news tied to a player on this roster; the rest of the feed is not Today's business.
  const rostered = useMemo(() => items.filter((item) => item.matched_player_id && item.roster_relationship), [items]);
  const groupedAlerts = useMemo(() => groupAlertsByType(rostered), [rostered]);
  const unread = useMemo(() => rostered.filter((item) => !item.read).length, [rostered]);
  useEffect(() => {
    unreadReported?.(unread);
  }, [unread, unreadReported]);

  const openAndMarkRead = (item: AlertItem) => {
    if (!item.read) {
      setItems((prev) => prev.map((row) => (row.alert_key === item.alert_key ? { ...row, read: true } : row)));
      // Never blocks or errors the tap: remembered locally and retried on the next load if offline.
      void currentAlertReadUserId().then((userId) => alertReadSync.markRead(userId, leagueId, item.alert_key));
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
    openQuickView(player, { leagueId, leagueName });
  };

  const { rows, total: rowTotal } = todayAlertRows(rostered);
  const [showAll, setShowAll] = useState(false);
  const open = showAll || forceOpen;
  const hasMore = rowTotal > rows.length || watchLines.length > 0 || recapReadyWeek != null || roundupNotice != null;
  const act = (row: TodayAlertRow) => {
    const item = items.find((i) => i.alert_key === row.alertKey);
    if (item) {
      if (!item.read) {
        setItems((prev) => prev.map((r) => (r.alert_key === item.alert_key ? { ...r, read: true } : r)));
        void currentAlertReadUserId().then((userId) => alertReadSync.markRead(userId, leagueId, item.alert_key));
      }
    }
    if (row.target === 'matchup') navigation.navigate('Matchup', { leagueId, leagueName, plan: 'all' });
    else if (row.link) void Linking.openURL(row.link);
  };

  if (loading && items.length === 0 && !error && !notReadyReason) return null;
  if (notReadyReason) return null;
  if (error) return <ErrorState compact title="Couldn't load alerts" message={error} onRetry={() => void load()} />;
  if (rows.length === 0 && !hasMore) return null;

  return (
    <View style={styles.section} testID="dashboard-alerts">
      <SectionHeading title={unread > 0 ? `Alerts · ${unread} new` : 'Alerts'} />
      {rows.length > 0 ? (
        <ExpandRowGroup accent={rows.some((r) => r.tone === 'danger') ? colors.danger : colors.accent} testID="alert-rows">
          {rows.map((r) => (
            <ExpandRow
              key={r.key}
              testID="alert-row"
              label={`${r.player.name}: ${r.reason}`}
              leading={<PlayerAvatarSlot player={{ id: r.player.id, name: r.player.name, position: r.player.position, team: r.player.team, tier: r.player.tier }} tier="row" nonInteractive="the row is the tap target" />}
              title={r.reason}
              caption={r.unread ? 'New' : undefined}
              action={<Button label={r.button} size="sm" onPress={() => act(r)} />}
            />
          ))}
        </ExpandRowGroup>
      ) : null}
      {hasMore ? (
        <PressableScale accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setShowAll((v) => !v)} style={styles.seeAll} testID="alerts-see-all">
          <AppText style={styles.seeAllText}>{open ? 'Hide alerts' : `All alerts (${rowTotal + watchLines.length})`}</AppText>
        </PressableScale>
      ) : null}
      <Collapse open={open}>
        <View style={styles.fullFeed}>
          {watchBody}
          {recapReadyWeek != null ? (
            <RecapReadyCard week={recapReadyWeek} onPress={() => navigation.navigate('News', { initialTab: 'league', leagueId, leagueName })} />
          ) : null}
          {roundupNotice ? (
            <RecapReadyCard
              week={roundupNotice.week}
              title={roundupNotice.title}
              subtitle={roundupNotice.body}
              icon="stats-chart-outline"
              onPress={() => navigation.navigate('News', { initialTab: 'league', leagueId, leagueName, recapsTab: 'roundup', week: roundupNotice.week })}
            />
          ) : null}
          {groupedAlerts.map((group) => {
            const accentColor = eventBadgeColors(colors)[group.eventType ?? ''] ?? colors.textSecondary;
            const icon = EVENT_BADGE_ICONS[group.eventType ?? ''] ?? 'information-circle-outline';
            return (
              <View key={`${group.eventType ?? 'other'}-${group.alerts[0]?.alert_key}`} style={styles.group}>
                <View style={styles.groupHeaderRow}>
                  <View style={[styles.groupAccentBar, { backgroundColor: accentColor }]} />
                  <Ionicons name={icon} size={13} color={accentColor} style={styles.groupIcon} />
                  <AppText style={[styles.groupLabel, { color: accentColor }]} numberOfLines={1}>
                    {eventTypeLabel(group.eventType)}
                  </AppText>
                </View>
                <View style={styles.groupCards}>
                  {group.alerts.map((alert) => (
                    <AccentCard key={alert.alert_key} accent={alert.read ? colors.border : accentColor} compact>
                      <AlertRow alert={alert} showDivider={false} onPress={() => openAndMarkRead(alert)} onPressPlayer={() => openPlayer(alert)} />
                    </AccentCard>
                  ))}
                </View>
              </View>
            );
          })}
        </View>
      </Collapse>
    </View>
  );
}

function AlertRow({
  alert,
  showDivider,
  onPress,
  onPressPlayer,
}: {
  alert: AlertItem;
  showDivider: boolean;
  onPress: () => void;
  onPressPlayer: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createRowStyles(colors), [colors]);
  const relationshipColors = rosterRelationshipColor(colors);
  // "Unconfirmed / speculative" used to sit in the same neutral gray line as
  // "Source: X", so a rumor read with the same visual confidence as a
  // confirmed report. Split out and given the same amber/bold caution
  // treatment PlayerDetailScreen's own news modal already uses for the
  // identical speculative flag (modalSpeculative) — not a new convention,
  // just applied consistently here too.
  const sourceBit = alert.source ? `Source: ${alert.source}` : null;
  // Alert rows have no visible affordance today (no chevron, no icon) even
  // though tapping one opens an external article — the Recap card in this
  // same list already signals "tap to open" with a trailing chevron, so
  // these rows looked like static text by comparison. Only show it when
  // there's actually somewhere to go; a link-less alert still just marks
  // read on tap.
  const opensLink = Boolean(alert.link);

  return (
    <PressableScale accessibilityRole="button"
      style={[styles.row, showDivider && styles.rowDivider, alert.read && styles.rowRead]}
      onPress={onPress}
    >
      <View style={styles.metaRow}>
        {!alert.read ? <View style={styles.unreadDot} /> : null}
        {alert.roster_relationship ? (
          <View
            style={[
              styles.relationshipPill,
              { backgroundColor: `${relationshipColors[alert.roster_relationship]}26` },
            ]}
          >
            <AppText
              style={[styles.relationshipPillText, { color: relationshipColors[alert.roster_relationship] }]}
            >
              {ROSTER_RELATIONSHIP_LABEL[alert.roster_relationship]}
            </AppText>
          </View>
        ) : null}
        <View style={styles.metaSpacer} />
        <AppText style={styles.time}>{relativeTime(alert.published_ts)}</AppText>
        {opensLink ? (
          <Ionicons name="chevron-forward" size={13} color={colors.textTertiary} style={styles.linkChevron} />
        ) : null}
      </View>
      {alert.matched_player ? (
        <PlayerIdentityRow
          playerId={alert.matched_player_id}
          name={alert.matched_player}
          position={alert.matched_player_position}
          team={alert.matched_player_team}
          tier={alert.matched_player_tier}
          onPress={alert.matched_player_id ? onPressPlayer : undefined}
        />
      ) : null}
      <AppText style={[styles.title, alert.read && styles.titleRead]} numberOfLines={2}>
        {alert.title}
      </AppText>
      {alert.summary ? (
        <AppText style={styles.summary} numberOfLines={3}>
          {alert.summary}
        </AppText>
      ) : null}
      {alert.speculative ? <AppText style={styles.speculative}>Unconfirmed / speculative</AppText> : null}
      {sourceBit ? <AppText style={styles.footerMeta}>{sourceBit}</AppText> : null}
    </PressableScale>
  );
}

function createRowStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { paddingVertical: 0 },
    rowRead: { opacity: 0.6 },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.xs },
    unreadDot: { width: 9, height: 9, borderRadius: 4.5, backgroundColor: colors.accent },
    relationshipPill: { borderRadius: radii.pill, paddingHorizontal: spacing.xs + 2, paddingVertical: 1 },
    relationshipPillText: { fontSize: 12, fontWeight: '800', letterSpacing: 0.3 },
    metaSpacer: { flex: 1 },
    time: { fontSize: 12.5, color: colors.textTertiary },
    linkChevron: { marginLeft: spacing.xs },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginTop: spacing.xs, marginBottom: 3 },
    titleRead: { fontWeight: '500', color: colors.textSecondary },
    summary: { fontSize: 14.5, color: colors.textSecondary, lineHeight: 20 },
    // Matches PlayerDetailScreen's modalSpeculative treatment for the same
    // flag — bold amber/"pending" tone (Magna Carta §3) rather than the
    // plain gray metadata line below it.
    speculative: { fontSize: 12.5, color: colors.premium, fontWeight: '700', marginTop: spacing.xs },
    footerMeta: { fontSize: 12.5, color: colors.textTertiary, marginTop: spacing.xs },
  });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { gap: spacing.sm },
    seeAll: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    seeAllText: { color: colors.accent, fontWeight: '700', fontSize: 14 },
    fullFeed: { gap: spacing.md },
    group: { marginBottom: spacing.xs },
    groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    groupAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
    groupIcon: { marginLeft: -2 },
    groupLabel: { flex: 1, fontSize: 13.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
    groupCards: { gap: spacing.sm },
  });
}

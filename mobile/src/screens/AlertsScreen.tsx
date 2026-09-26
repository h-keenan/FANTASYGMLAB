import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, Linking, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type AlertItem, type RankedPlayer, type RosterRelationship } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Alerts'>;
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

export default function AlertsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<AlertItem[]>([]);
  const [recapReadyWeek, setRecapReadyWeek] = useState<number | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Alerts', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

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

  const groupedAlerts = useMemo(() => groupAlertsByType(items), [items]);

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
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't load alerts for this league."}
        </AppText>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`Recent news about players on your roster in ${leagueName} — injury, role, transaction, and off-field signal only.`}
      />

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        data={groupedAlerts}
        keyExtractor={(group, index) => `${group.eventType ?? 'other'}-${group.alerts[0]?.alert_key ?? index}`}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          recapReadyWeek != null ? (
            <TouchableOpacity onPress={() => navigation.navigate('Recap', { leagueId, leagueName })}>
              <AnimatedCard glow style={styles.recapCard}>
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
        renderItem={({ item: group }) => {
          const accentColor = eventBadgeColors(colors)[group.eventType ?? ''] ?? colors.textSecondary;
          const icon = EVENT_BADGE_ICONS[group.eventType ?? ''] ?? 'information-circle-outline';
          return (
            <View style={styles.group}>
              <View style={styles.groupHeaderRow}>
                <View style={[styles.groupAccentBar, { backgroundColor: accentColor }]} />
                <Ionicons name={icon} size={13} color={accentColor} style={styles.groupIcon} />
                <AppText style={[styles.groupLabel, { color: accentColor }]} numberOfLines={1}>
                  {eventTypeLabel(group.eventType)}
                </AppText>
              </View>
              <AnimatedCard style={styles.groupCard}>
                {group.alerts.map((alert, index) => (
                  <AlertRow
                    key={alert.alert_key}
                    alert={alert}
                    showDivider={index < group.alerts.length - 1}
                    onPress={() => openAndMarkRead(alert)}
                    onPressPlayer={() => openPlayer(alert)}
                  />
                ))}
              </AnimatedCard>
            </View>
          );
        }}
      />
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
    <TouchableOpacity
      style={[styles.row, showDivider && styles.rowDivider, alert.read && styles.rowRead]}
      onPress={onPress}
      activeOpacity={0.7}
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
    </TouchableOpacity>
  );
}

function createRowStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { paddingVertical: spacing.sm + 2 },
    rowRead: { opacity: 0.6 },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.xs },
    unreadDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: colors.accent },
    relationshipPill: { borderRadius: radii.pill, paddingHorizontal: spacing.xs + 2, paddingVertical: 1 },
    relationshipPillText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
    metaSpacer: { flex: 1 },
    time: { fontSize: 11, color: colors.textTertiary },
    linkChevron: { marginLeft: spacing.xs },
    title: { fontSize: 14.5, fontWeight: '600', color: colors.textPrimary, marginTop: spacing.xs, marginBottom: 3 },
    titleRead: { fontWeight: '500', color: colors.textSecondary },
    summary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    // Matches PlayerDetailScreen's modalSpeculative treatment for the same
    // flag — bold amber/"pending" tone (Magna Carta §3) rather than the
    // plain gray metadata line below it.
    speculative: { fontSize: 11, color: colors.premium, fontWeight: '700', marginTop: spacing.xs },
    footerMeta: { fontSize: 11, color: colors.textTertiary, marginTop: spacing.xs },
  });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.background,
      padding: spacing.xl,
    },
    notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
    listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3 },
    recapCard: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: spacing.md,
      marginBottom: spacing.md,
    },
    recapIconDisc: { marginRight: spacing.sm },
    recapTextGroup: { flex: 1 },
    recapTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    recapSubtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    group: { marginBottom: spacing.md },
    groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    groupAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
    groupIcon: { marginLeft: -2 },
    groupLabel: {
      flex: 1,
      fontSize: 12,
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
    error: {
      color: colors.danger,
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.sm,
    },
  });
}

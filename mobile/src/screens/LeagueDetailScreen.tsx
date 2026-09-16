import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import TeamAvatar from '../components/TeamAvatar';
import { api } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface TeamRow {
  rosterId: number | string;
  teamName: string;
  avatarId: string;
  playerIds: string[];
  isMine: boolean;
}

interface LeagueSummary {
  season: string;
  week: string;
  teamCount: string;
  scoring: string;
}

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const QUICK_ACTIONS: Array<{ label: string; route: string; icon: IconName }> = [
  { label: 'Next Move', route: 'Dashboard', icon: 'flash-outline' },
  { label: 'Players', route: 'Players', icon: 'people-outline' },
  { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline' },
  { label: 'Trade\nAnalyzer', route: 'TradeAnalyzer', icon: 'git-compare-outline' },
  { label: 'GM Targets', route: 'GmTargets', icon: 'bookmark-outline' },
  { label: 'Recap', route: 'Recap', icon: 'newspaper-outline' },
  { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline' },
];

function scoringLabel(scoringSettings: Record<string, unknown> | undefined): string {
  const rec = Number(scoringSettings?.rec ?? 0);
  if (rec >= 1) return 'PPR';
  if (rec > 0) return 'Half PPR';
  return 'Standard';
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [summary, setSummary] = useState<LeagueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: leagueName });
  }, [leagueName, navigation]);

  useEffect(() => {
    void setLastLeague({ leagueId, leagueName });
  }, [leagueId, leagueName]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [profilesResult, rostersResult, myRosterResult, leagueResult] = await Promise.all([
          api.getLeagueTeamProfiles(leagueId),
          api.getLeagueRosters(leagueId),
          api.getMyRoster(leagueId).catch(() => ({ ok: true as const, roster: null, reason: '' as const })),
          api.getLeague(leagueId).catch(() => null),
        ]);
        if (cancelled) return;

        const myRosterId = myRosterResult.roster
          ? String(myRosterResult.roster.roster_id ?? '')
          : '';

        const rows: TeamRow[] = rostersResult.rosters.map((roster) => {
          const rosterId = String(roster.roster_id ?? '');
          const players = Array.isArray(roster.players) ? roster.players : [];
          const profile = profilesResult.profiles[rosterId];
          return {
            rosterId,
            teamName: profile?.team_name || 'Unclaimed team',
            avatarId: profile?.avatar_id || '',
            playerIds: players.map(String),
            isMine: Boolean(myRosterId) && rosterId === myRosterId,
          };
        });
        rows.sort((a, b) => Number(b.isMine) - Number(a.isMine));
        setTeams(rows);

        if (leagueResult?.league) {
          const league = leagueResult.league;
          const settings = (league.settings as Record<string, unknown>) ?? {};
          setSummary({
            season: String(league.season ?? '—'),
            week: settings.leg ? String(settings.leg) : '—',
            teamCount: String(league.total_rosters ?? rows.length ?? '—'),
            scoring: scoringLabel(league.scoring_settings as Record<string, unknown>),
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load league.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={styles.listContent}
      data={teams}
      keyExtractor={(item) => String(item.rosterId)}
      ListHeaderComponent={
        <>
          {summary ? (
            <View style={styles.summaryRow}>
              <View style={styles.summaryStat}>
                <Text style={styles.summaryValue}>{summary.season}</Text>
                <Text style={styles.summaryLabel}>Season</Text>
              </View>
              <View style={styles.summaryStat}>
                <Text style={styles.summaryValue}>{summary.week}</Text>
                <Text style={styles.summaryLabel}>Week</Text>
              </View>
              <View style={styles.summaryStat}>
                <Text style={styles.summaryValue}>{summary.teamCount}</Text>
                <Text style={styles.summaryLabel}>Teams</Text>
              </View>
              <View style={styles.summaryStat}>
                <Text style={styles.summaryValue}>{summary.scoring}</Text>
                <Text style={styles.summaryLabel}>Scoring</Text>
              </View>
            </View>
          ) : null}

          <View style={styles.quickActionsGrid}>
            {QUICK_ACTIONS.map((action) => (
              <TouchableOpacity
                key={action.route}
                style={styles.quickActionTile}
                onPress={() =>
                  (navigation.navigate as (name: string, params?: object) => void)(action.route, {
                    leagueId,
                    leagueName,
                  })
                }
              >
                <Ionicons name={action.icon} size={22} color={colors.accent} />
                <Text style={styles.quickActionLabel}>{action.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.sectionTitle}>Teams</Text>
        </>
      }
      renderItem={({ item }) => (
        <AnimatedCard
          style={StyleSheet.flatten([styles.card, item.isMine && styles.cardMine])}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: item.teamName,
              playerIds: item.playerIds,
              leagueId,
              leagueName,
            })
          }
        >
          <View style={styles.row}>
            <TeamAvatar avatarId={item.avatarId} size={36} style={styles.avatar} />
            <View style={styles.ownerGroup}>
              <Text style={styles.owner} numberOfLines={1}>
                {item.teamName}
              </Text>
              {item.isMine ? (
                <View style={styles.mineBadge}>
                  <Text style={styles.mineBadgeText}>You</Text>
                </View>
              ) : null}
            </View>
            <View style={styles.countPill}>
              <Text style={styles.count}>{item.playerIds.length}</Text>
            </View>
          </View>
        </AnimatedCard>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { backgroundColor: colors.background },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  summaryRow: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  summaryStat: { flex: 1, alignItems: 'center' },
  summaryValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  summaryLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  quickActionTile: {
    width: '31%',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    alignItems: 'center',
    gap: spacing.xs,
  },
  quickActionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  card: { padding: spacing.lg },
  cardMine: { borderWidth: 2, borderColor: colors.accent },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: { marginRight: spacing.sm },
  ownerGroup: { flex: 1, flexDirection: 'row', alignItems: 'center', marginRight: spacing.sm },
  owner: { fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm, flexShrink: 1 },
  mineBadge: {
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  mineBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  countPill: {
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    minWidth: 28,
    alignItems: 'center',
  },
  count: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  error: { color: colors.danger, textAlign: 'center' },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
  },
});

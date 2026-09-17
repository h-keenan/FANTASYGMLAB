import React, { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import TeamAvatar from '../components/TeamAvatar';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Teams'>;

interface TeamRow {
  rosterId: number | string;
  teamName: string;
  avatarId: string;
  playerIds: string[];
  isMine: boolean;
  powerRank: number | null;
  recordLabel: string | null;
  archetypeLabel: string | null;
}

export default function TeamsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Teams', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const [profilesResult, rostersResult, myRosterResult, rankingsResult] = await Promise.all([
            api.getLeagueTeamProfiles(leagueId),
            api.getLeagueRosters(leagueId),
            api.getMyRoster(leagueId).catch(() => ({ ok: true as const, roster: null, reason: '' as const })),
            api
              .getLeagueTeamRankings(leagueId)
              .catch(() => ({ ok: true as const, teams: [], reason: 'unavailable' })),
          ]);
          if (cancelled) return;

          const myRosterId = myRosterResult.roster ? String(myRosterResult.roster.roster_id ?? '') : '';
          const rankingsByRoster = new Map(rankingsResult.teams.map((team) => [team.roster_id, team]));

          const rows: TeamRow[] = rostersResult.rosters.map((roster) => {
            const rosterId = String(roster.roster_id ?? '');
            const players = Array.isArray(roster.players) ? roster.players : [];
            const profile = profilesResult.profiles[rosterId];
            const ranking = rankingsByRoster.get(rosterId);
            return {
              rosterId,
              teamName: profile?.team_name || 'Unclaimed team',
              avatarId: profile?.avatar_id || '',
              playerIds: players.map(String),
              isMine: Boolean(myRosterId) && rosterId === myRosterId,
              powerRank: ranking?.power_rank ?? null,
              recordLabel: ranking?.record_label ?? null,
              archetypeLabel: ranking?.archetype_label ?? null,
            };
          });
          rows.sort((a, b) => {
            if (a.isMine !== b.isMine) return Number(b.isMine) - Number(a.isMine);
            if (a.powerRank != null && b.powerRank != null) return a.powerRank - b.powerRank;
            return 0;
          });
          setTeams(rows);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load teams.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      void load();
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
  );

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
    <View style={styles.root}>
      <GridBackground />
      <FlatList
      style={styles.list}
      contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
      data={teams}
      keyExtractor={(item) => String(item.rosterId)}
      renderItem={({ item }) => (
        <AnimatedCard
          style={StyleSheet.flatten([styles.card, item.isMine && styles.cardMine])}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: item.teamName,
              playerIds: item.playerIds,
              leagueId,
              leagueName,
              rosterId: String(item.rosterId),
            })
          }
        >
          <View style={styles.row}>
            <TeamAvatar avatarId={item.avatarId} size={36} style={styles.avatar} />
            <View style={styles.ownerGroup}>
              <View style={styles.nameRow}>
                <Text style={styles.owner} numberOfLines={1}>
                  {item.teamName}
                </Text>
                {item.isMine ? (
                  <View style={styles.mineBadge}>
                    <Text style={styles.mineBadgeText}>You</Text>
                  </View>
                ) : null}
              </View>
              {item.recordLabel ? <Text style={styles.record}>{item.recordLabel}</Text> : null}
              {item.archetypeLabel ? (
                <View style={styles.archetypeBadge}>
                  <Text style={styles.archetypeBadgeText} numberOfLines={1}>
                    {item.archetypeLabel}
                  </Text>
                </View>
              ) : null}
            </View>
            {item.powerRank != null ? (
              <View style={styles.rankPill}>
                <Text style={styles.rankLabel}>POWER</Text>
                <Text style={styles.rankValue}>#{item.powerRank}</Text>
              </View>
            ) : (
              <View style={styles.countPill}>
                <Text style={styles.count}>{item.playerIds.length}</Text>
              </View>
            )}
          </View>
        </AnimatedCard>
      )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  card: { padding: spacing.lg },
  cardMine: { borderWidth: 2, borderColor: colors.accent },
  row: { flexDirection: 'row', alignItems: 'center' },
  avatar: { marginRight: spacing.sm },
  ownerGroup: { flex: 1, marginRight: spacing.sm },
  nameRow: { flexDirection: 'row', alignItems: 'center' },
  owner: { fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm, flexShrink: 1 },
  record: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  archetypeBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginTop: spacing.xs,
  },
  archetypeBadgeText: { fontSize: 10, fontWeight: '700', color: colors.badgeText },
  rankPill: {
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    alignItems: 'center',
    minWidth: 52,
  },
  rankLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.4,
  },
  rankValue: { fontSize: 15, fontWeight: '700', color: colors.accent },
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
});

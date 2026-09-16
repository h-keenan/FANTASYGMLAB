import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import TeamAvatar from '../components/TeamAvatar';
import { api } from '../lib/api';
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
}

export default function TeamsScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Teams', leagueName);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [profilesResult, rostersResult, myRosterResult] = await Promise.all([
          api.getLeagueTeamProfiles(leagueId),
          api.getLeagueRosters(leagueId),
          api.getMyRoster(leagueId).catch(() => ({ ok: true as const, roster: null, reason: '' as const })),
        ]);
        if (cancelled) return;

        const myRosterId = myRosterResult.roster ? String(myRosterResult.roster.roster_id ?? '') : '';

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
  card: { padding: spacing.lg },
  cardMine: { borderWidth: 2, borderColor: colors.accent },
  row: { flexDirection: 'row', alignItems: 'center' },
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
});

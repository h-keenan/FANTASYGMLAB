import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface TeamRow {
  rosterId: number | string;
  ownerName: string;
  playerIds: string[];
  isMine: boolean;
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
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
        const [usersResult, rostersResult, myRosterResult] = await Promise.all([
          api.getLeagueUsers(leagueId),
          api.getLeagueRosters(leagueId),
          api.getMyRoster(leagueId).catch(() => ({ ok: true as const, roster: null, reason: '' as const })),
        ]);
        if (cancelled) return;

        const usersById = new Map<string, string>();
        for (const user of usersResult.users) {
          const id = String(user.user_id ?? '');
          const name = String(
            user.display_name ?? user.username ?? 'Unknown owner',
          );
          if (id) usersById.set(id, name);
        }

        const myRosterId = myRosterResult.roster
          ? String(myRosterResult.roster.roster_id ?? '')
          : '';

        const rows: TeamRow[] = rostersResult.rosters.map((roster) => {
          const ownerId = String(roster.owner_id ?? '');
          const players = Array.isArray(roster.players) ? roster.players : [];
          const rosterId = String(roster.roster_id ?? '');
          return {
            rosterId,
            ownerName: usersById.get(ownerId) ?? 'Unclaimed team',
            playerIds: players.map(String),
            isMine: Boolean(myRosterId) && rosterId === myRosterId,
          };
        });
        rows.sort((a, b) => Number(b.isMine) - Number(a.isMine));
        setTeams(rows);
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
      ListHeaderComponent={<Text style={styles.sectionTitle}>Teams</Text>}
      renderItem={({ item }) => (
        <AnimatedCard
          style={StyleSheet.flatten([styles.card, item.isMine && styles.cardMine])}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: item.ownerName,
              playerIds: item.playerIds,
            })
          }
        >
          <View style={styles.row}>
            <View style={styles.ownerGroup}>
              <Text style={styles.owner} numberOfLines={1}>
                {item.ownerName}
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
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
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

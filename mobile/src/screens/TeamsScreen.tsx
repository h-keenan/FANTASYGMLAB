import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import TeamAvatar from '../components/TeamAvatar';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
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
  tradeTendency: string | null;
}

export default function TeamsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
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
              tradeTendency: ranking?.trade_tendency && ranking.trade_tendency !== 'Neutral' ? ranking.trade_tendency : null,
            };
          });
          // Pure Power Rank order — no longer pins the caller's own team
          // first, since that made a rank-4 team appear above rank-1 with
          // no explanation. The "You" badge + glow accent below is how a
          // user finds their own row now instead of it always being #1 in
          // the list regardless of rank.
          rows.sort((a, b) => {
            if (a.powerRank == null && b.powerRank == null) return 0;
            if (a.powerRank == null) return 1;
            if (b.powerRank == null) return -1;
            return a.powerRank - b.powerRank;
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
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenHero title="TEAMS" subtitle={leagueName} />
      <FlatList
      style={styles.list}
      contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
      data={teams}
      keyExtractor={(item) => String(item.rosterId)}
      renderItem={({ item }) => (
        <AnimatedCard
          glow={item.isMine}
          style={styles.card}
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
                <AppText style={styles.owner} numberOfLines={1}>
                  {item.teamName}
                </AppText>
                {item.isMine ? (
                  <View style={styles.mineBadge}>
                    <AppText style={styles.mineBadgeText}>You</AppText>
                  </View>
                ) : null}
              </View>
              {item.recordLabel ? <AppText style={styles.record}>{item.recordLabel}</AppText> : null}
              {item.archetypeLabel ? (
                <View style={styles.archetypeBadge}>
                  <AppText style={styles.archetypeBadgeText} numberOfLines={1}>
                    {item.archetypeLabel}
                  </AppText>
                </View>
              ) : null}
              {item.tradeTendency ? (
                <View style={styles.tendencyRow}>
                  <Ionicons
                    name={item.tradeTendency === 'Seller' ? 'trending-down' : 'trending-up'}
                    size={11}
                    color={item.tradeTendency === 'Seller' ? colors.accentSoft : colors.premium}
                  />
                  <AppText
                    style={[
                      styles.tendencyText,
                      { color: item.tradeTendency === 'Seller' ? colors.accentSoft : colors.premium },
                    ]}
                    numberOfLines={1}
                  >
                    Real history of {item.tradeTendency === 'Seller' ? 'selling' : 'buying'}
                  </AppText>
                </View>
              ) : null}
            </View>
            {item.powerRank != null ? (
              <View style={[styles.rankPill, item.powerRank === 1 && styles.rankPillFirst]}>
                {item.powerRank === 1 ? (
                  <Ionicons name="trophy" size={13} color={colors.premium} style={styles.rankTrophy} />
                ) : (
                  <AppText style={styles.rankLabel}>POWER</AppText>
                )}
                <AppText style={[styles.rankValue, item.powerRank === 1 && styles.rankValueFirst]}>
                  #{item.powerRank}
                </AppText>
              </View>
            ) : (
              <View style={styles.countPill}>
                <AppText style={styles.count}>{item.playerIds.length}</AppText>
              </View>
            )}
          </View>
        </AnimatedCard>
      )}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
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
  tendencyRow: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 3 },
  tendencyText: { fontSize: 11, fontWeight: '600' },
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
  // League #1 gets the same premium/gold hue as an award badge instead of
  // the standard accent — a leaderboard's top spot should read as "the"
  // rank at a glance, not just another pill in the same color as #2-#12.
  rankPillFirst: { backgroundColor: `${colors.premium}1F`, borderWidth: 1, borderColor: `${colors.premium}80` },
  rankTrophy: { marginBottom: 1 },
  rankValueFirst: { color: colors.premium },
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
}

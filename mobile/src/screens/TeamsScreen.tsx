import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TeamAvatar from '../components/TeamAvatar';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { percentileColor, percentileFromRank } from '../lib/percentile';
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
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<TeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Teams', leagueName);

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
          // no explanation. The "You" badge + left-accent row below is how a
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

  // Percentile denominator is the count of teams the backend actually ranked
  // (not every roster — an unclaimed team has no power_rank and shouldn't
  // shrink the league size other teams are compared against).
  const rankedTeamCount = useMemo(() => teams.filter((team) => team.powerRank != null).length, [teams]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <FlatList
        style={styles.list}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        data={teams}
        keyExtractor={(item) => String(item.rosterId)}
        ListHeaderComponent={
          <View style={styles.infoNoteWrap}>
            <ScreenInfoNote
              label="How Power Rank works"
              text="Teams are ordered by Power Rank — roster strength (starters + bench), not record — so you can see exactly where every team in the league stacks up. Your team is marked You and highlighted below."
            />
          </View>
        }
        renderItem={({ item, index }) => (
          <TeamRowCard
            item={item}
            isFirst={index === 0}
            isLast={index === teams.length - 1}
            rankedTeamCount={rankedTeamCount}
            colors={colors}
            styles={styles}
            onPress={() =>
              navigation.navigate('TeamRoster', {
                ownerName: item.teamName,
                playerIds: item.playerIds,
                leagueId,
                leagueName,
                rosterId: String(item.rosterId),
              })
            }
          />
        )}
      />
    </View>
  );
}

function TeamRowCard({
  item,
  isFirst,
  isLast,
  rankedTeamCount,
  colors,
  styles,
  onPress,
}: {
  item: TeamRow;
  isFirst: boolean;
  isLast: boolean;
  rankedTeamCount: number;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onPress: () => void;
}) {
  const isChampion = item.powerRank === 1;
  const rankPercentile = percentileFromRank(item.powerRank, rankedTeamCount);
  // League #1 keeps the same premium/gold hue as an award badge instead of
  // the percentile ramp — a leaderboard's top spot should read as "the"
  // rank at a glance. Every other rank uses the shared percentile color
  // ramp (§27) so a bottom-of-the-league team reads as weak (red/amber)
  // and a near-top team reads as strong (green), not one flat accent color
  // regardless of where in the pack it actually sits.
  const rankColor = isChampion ? colors.premium : percentileColor(rankPercentile, colors);

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
        item.isMine && styles.rowMine,
      ]}
    >
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
        <View style={[styles.rankPill, isChampion && styles.rankPillFirst, { borderColor: `${rankColor}80` }]}>
          {isChampion ? (
            <Ionicons name="trophy" size={13} color={rankColor} style={styles.rankTrophy} />
          ) : (
            <AppText style={styles.rankLabel}>POWER</AppText>
          )}
          <AppText style={[styles.rankValue, { color: rankColor }]}>#{item.powerRank}</AppText>
        </View>
      ) : (
        <View style={styles.countPill}>
          <AppText style={styles.count}>{item.playerIds.length}</AppText>
        </View>
      )}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg },
  infoNoteWrap: { marginBottom: spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  // Continuous grouped surface with internal dividers (Magna Carta §12)
  // instead of a separately-bordered, separately-shadowed card per team —
  // every team is a peer row in one leaderboard, not N independent modules.
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
  },
  rowFirst: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
  rowLast: { borderBottomWidth: StyleSheet.hairlineWidth * 1.5, borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  // The user's own row gets a cyan left rail + faint tint — the same
  // badge-tint token used elsewhere for cyan emphasis (§14: cyan reserved
  // for selection/important-module cues), not a page-specific color.
  rowMine: {
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    backgroundColor: colors.badgeBackground,
  },
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
    borderWidth: 1,
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
  rankValue: { fontSize: 15, fontWeight: '700' },
  // League #1 gets the same premium/gold hue as an award badge instead of
  // the standard accent — a leaderboard's top spot should read as "the"
  // rank at a glance, not just another pill in the same color scheme as
  // the rest of the pack.
  rankPillFirst: { backgroundColor: `${colors.premium}1F` },
  rankTrophy: { marginBottom: 1 },
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

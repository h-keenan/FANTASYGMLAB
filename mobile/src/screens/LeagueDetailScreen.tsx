import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import TeamAvatar from '../components/TeamAvatar';
import { api, type DashboardItem } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { gradients, radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { LinearGradient } from 'expo-linear-gradient';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface LeagueSummary {
  season: string;
  week: string;
  teamCount: string;
  scoring: string;
}

interface MyTeamInfo {
  teamName: string;
  avatarId: string;
  playerCount: number;
  playerIds: string[];
  rosterId: string;
}

function scoringLabel(scoringSettings: Record<string, unknown> | undefined): string {
  const rec = Number(scoringSettings?.rec ?? 0);
  if (rec >= 1) return 'PPR';
  if (rec > 0) return 'Half PPR';
  return 'Standard';
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [summary, setSummary] = useState<LeagueSummary | null>(null);
  const [dashboardItems, setDashboardItems] = useState<DashboardItem[]>([]);
  const [dashboardQuiet, setDashboardQuiet] = useState(false);
  const [myTeam, setMyTeam] = useState<MyTeamInfo | null>(null);
  const [recapReady, setRecapReady] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'League Overview', leagueName);

  useEffect(() => {
    navigation.setOptions({ headerRight: () => <GmStanceHeaderButton leagueId={leagueId} /> });
  }, [navigation, leagueId]);

  useEffect(() => {
    void setLastLeague({ leagueId, leagueName });
  }, [leagueId, leagueName]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const [leagueResult, dashboardResult, myRosterResult, profilesResult, recapResult] =
            await Promise.all([
              api.getLeague(leagueId).catch(() => null),
              api.getLeagueDashboard(leagueId).catch(() => null),
              api.getMyRoster(leagueId).catch(() => null),
              api.getLeagueTeamProfiles(leagueId).catch(() => null),
              api.getLeagueRecap(leagueId).catch(() => null),
            ]);
          if (cancelled) return;

          if (leagueResult?.league) {
            const league = leagueResult.league;
            const settings = (league.settings as Record<string, unknown>) ?? {};
            setSummary({
              season: String(league.season ?? '—'),
              week: settings.leg ? String(settings.leg) : '—',
              teamCount: String(league.total_rosters ?? '—'),
              scoring: scoringLabel(league.scoring_settings as Record<string, unknown>),
            });
          }

          if (dashboardResult) {
            setDashboardItems(dashboardResult.items ?? []);
            setDashboardQuiet(dashboardResult.quiet);
          }

          const roster = myRosterResult?.roster as { roster_id?: unknown; players?: unknown } | null | undefined;
          if (roster && profilesResult) {
            const rosterId = String(roster.roster_id ?? '');
            const profile = profilesResult.profiles[rosterId];
            const playerIds = Array.isArray(roster.players) ? roster.players.map(String) : [];
            setMyTeam({
              teamName: profile?.team_name || 'Your team',
              avatarId: profile?.avatar_id || '',
              playerCount: playerIds.length,
              playerIds,
              rosterId,
            });
          }

          if (recapResult?.recap && !recapResult.recap.incomplete) {
            setRecapReady(recapResult.recap.week);
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
    }, [leagueId]),
  );

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

  const heroHeadline = dashboardQuiet || dashboardItems.length === 0
    ? 'Quiet week — nothing urgent'
    : `${dashboardItems.length} priority move${dashboardItems.length === 1 ? '' : 's'} identified`;
  const heroSubtitle = dashboardItems[0]?.headline ?? 'Your roster looks steady right now.';

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.list} contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenHero title="LEAGUE OVERVIEW" subtitle={leagueName} />
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => navigation.navigate('Dashboard', { leagueId, leagueName })}
      >
        <LinearGradient colors={gradients.hero} style={styles.heroCard}>
          <AppText style={styles.heroKicker}>TODAY'S GAME PLAN</AppText>
          <AppText style={styles.heroHeadline}>{heroHeadline}</AppText>
          <AppText style={styles.heroSubtitle} numberOfLines={1}>
            {heroSubtitle}
          </AppText>
          <View style={styles.heroButton}>
            <AppText style={styles.heroButtonText}>View Plan</AppText>
          </View>
        </LinearGradient>
      </TouchableOpacity>

      {summary ? (
        <View style={styles.contextRow}>
          <Ionicons name="calendar-outline" size={13} color={colors.textTertiary} />
          <AppText style={styles.contextText}>
            {summary.season} · Week {summary.week} · {summary.teamCount} teams · {summary.scoring}
          </AppText>
        </View>
      ) : null}

      {myTeam ? (
        <AnimatedCard
          style={styles.stripCard}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: myTeam.teamName,
              playerIds: myTeam.playerIds,
              leagueId,
              leagueName,
              rosterId: myTeam.rosterId,
            })
          }
        >
          <TeamAvatar avatarId={myTeam.avatarId} size={36} style={styles.stripAvatar} />
          <View style={styles.stripTextGroup}>
            <View style={styles.stripNameRow}>
              <AppText style={styles.stripName} numberOfLines={1}>
                {myTeam.teamName}
              </AppText>
              <View style={styles.youBadge}>
                <AppText style={styles.youBadgeText}>You</AppText>
              </View>
            </View>
          </View>
          <AppText style={styles.stripValue}>{myTeam.playerCount}</AppText>
          <AppText style={styles.stripValueLabel}>PLAYERS</AppText>
        </AnimatedCard>
      ) : null}

      {recapReady !== null ? (
        <AnimatedCard
          style={styles.stripCard}
          onPress={() => navigation.navigate('Recap', { leagueId, leagueName })}
        >
          <IconCircle name="newspaper-outline" color={colors.accent} size={36} />
          <AppText style={styles.stripTextGroup2}>Week {recapReady} recap ready</AppText>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </AnimatedCard>
      ) : null}
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  heroCard: {
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    minHeight: 132,
  },
  heroKicker: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.8 },
  heroHeadline: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginTop: 4 },
  heroSubtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  heroButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    marginTop: spacing.md,
  },
  heroButtonText: { fontSize: 12, fontWeight: '700', color: colors.background },
  contextRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  contextText: { fontSize: 12, fontWeight: '500', color: colors.textSecondary, letterSpacing: 0.2 },
  stripCard: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.sm },
  stripAvatar: {},
  stripTextGroup: { flex: 1 },
  stripNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  stripName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  youBadge: { backgroundColor: colors.accent, borderRadius: radii.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  youBadgeText: { color: colors.background, fontSize: 10, fontWeight: '700' },
  stripValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  stripValueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, marginLeft: 4 },
  stripTextGroup2: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  error: { color: colors.danger, textAlign: 'center' },
  });
}

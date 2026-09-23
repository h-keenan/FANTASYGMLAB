import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import RecapSharePreviewModal from '../components/RecapSharePreviewModal';
import RecapTradeDetailModal from '../components/RecapTradeDetailModal';
import { api, type RecapStory, type WeeklyRecap } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Recap'>;

function storyMeta(colors: ThemeColors): Record<
  string,
  { icon: React.ComponentProps<typeof Ionicons>['name']; color: string }
> {
  return {
    performance: { icon: 'trophy', color: colors.premium },
    performance_low: { icon: 'trending-down', color: colors.premium },
    matchup: { icon: 'flame', color: colors.danger },
    matchup_close: { icon: 'pulse', color: colors.danger },
    waiver: { icon: 'cash-outline', color: colors.success },
    waiver_low: { icon: 'pricetag-outline', color: colors.success },
    trade: { icon: 'swap-horizontal', color: colors.accent },
    activity: { icon: 'repeat', color: colors.violet },
    activity_low: { icon: 'moon-outline', color: colors.violet },
    roster_riser: { icon: 'trending-up', color: colors.accent },
  };
}
function defaultStoryMeta(colors: ThemeColors) {
  return { icon: 'newspaper-outline' as const, color: colors.textSecondary };
}

export default function RecapScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [recap, setRecap] = useState<WeeklyRecap | null>(null);
  const [maxCompletedWeek, setMaxCompletedWeek] = useState(0);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [notReady, setNotReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [tradeStory, setTradeStory] = useState<RecapStory | null>(null);
  const [rosterMap, setRosterMap] = useState<Record<string, { playerIds: string[]; teamName: string }>>({});

  useScreenHeaderTitle(navigation, 'Recap', leagueName);

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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await api.getLeagueRecap(leagueId, selectedWeek != null ? { week: selectedWeek } : undefined);
        if (cancelled) return;
        setMaxCompletedWeek(result.max_completed_week);
        if (result.recap) {
          setRecap(result.recap);
          setNotReady(false);
        } else {
          setNotReady(true);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load recap.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, selectedWeek]);

  // Story cards navigate to TeamRoster, which (like TeamsScreen/LeagueDetailScreen)
  // needs a pre-fetched playerIds list per roster_id — best-effort: a story
  // card whose roster isn't found here still navigates, just with an empty
  // roster (TeamRosterScreen renders its own "no player data" empty state).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [rostersResult, profilesResult] = await Promise.all([
          api.getLeagueRosters(leagueId),
          api.getLeagueTeamProfiles(leagueId),
        ]);
        if (cancelled) return;
        const map: Record<string, { playerIds: string[]; teamName: string }> = {};
        for (const roster of rostersResult.rosters) {
          const rosterId = String(roster.roster_id ?? '');
          if (!rosterId) continue;
          const players = Array.isArray(roster.players) ? roster.players : [];
          map[rosterId] = {
            playerIds: players.map(String),
            teamName: profilesResult.profiles[rosterId]?.team_name || '',
          };
        }
        setRosterMap(map);
      } catch {
        // Non-fatal — cards with a primary_roster_id still navigate below,
        // TeamRosterScreen just starts from an empty roster in that case.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (loading && !recap) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  const weekPicker =
    maxCompletedWeek > 1 ? (
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.weekPickerRow}>
        {Array.from({ length: maxCompletedWeek }, (_, i) => i + 1).map((weekNum) => {
          const active = (selectedWeek ?? maxCompletedWeek) === weekNum;
          return (
            <TouchableOpacity
              key={weekNum}
              style={[styles.weekPill, active && styles.weekPillActive]}
              onPress={() => setSelectedWeek(weekNum)}
            >
              <AppText style={[styles.weekPillText, active && styles.weekPillTextActive]}>Wk {weekNum}</AppText>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    ) : null;

  if (notReady || !recap) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        {weekPicker}
        <View style={styles.center}>
          <AppText style={styles.notReadyText}>
            No recap is ready yet — check back after this week's matchups finish scoring.
          </AppText>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      {weekPicker}
      {loading ? (
        <View style={styles.inlineLoadingRow}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : (
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <View style={styles.headerRow}>
        <View style={styles.headerTextGroup}>
          <AppText style={styles.kicker}>LEAGUE MEMORY</AppText>
          <AppText style={styles.headline}>{recap.headline}</AppText>
        </View>
        {!recap.incomplete ? (
          <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
            <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
            <AppText style={styles.shareButtonText}>Share</AppText>
          </TouchableOpacity>
        ) : null}
      </View>
      {recap.incomplete ? (
        <AppText style={styles.incompleteNotice}>{recap.empty_reason || 'Not enough historical data yet.'}</AppText>
      ) : (
        recap.stories.map((story, index) => {
          let onPress: (() => void) | undefined;
          if (story.story_type === 'trade') {
            onPress = () => setTradeStory(story);
          } else if (story.primary_roster_id) {
            const rosterId = story.primary_roster_id;
            const rosterEntry = rosterMap[rosterId];
            onPress = () =>
              navigation.navigate('TeamRoster', {
                ownerName: rosterEntry?.teamName || story.primary_team,
                playerIds: rosterEntry?.playerIds ?? [],
                leagueId,
                leagueName,
                rosterId,
              });
          }
          return <StoryCard key={`${story.story_type}-${index}`} story={story} onPress={onPress} />;
        })
      )}
      </ScrollView>
      )}
      <RecapSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueName={leagueName}
        recap={recap}
      />
      <RecapTradeDetailModal visible={tradeStory != null} onClose={() => setTradeStory(null)} story={tradeStory} />
    </View>
  );
}

function StoryCard({ story, onPress }: { story: RecapStory; onPress?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = storyMeta(colors)[story.story_type] ?? defaultStoryMeta(colors);
  const isMatchup = story.story_type === 'matchup' || story.story_type === 'matchup_close';
  const isTrade = story.story_type === 'trade';

  return (
    <AnimatedCard style={styles.storyCard}>
      <TouchableOpacity onPress={onPress} disabled={!onPress} activeOpacity={0.75}>
      <View style={styles.storyHeaderRow}>
        <IconCircle name={meta.icon} color={meta.color} size={40} />
        <View style={styles.storyTextGroup}>
          <AppText style={[styles.storyKicker, { color: meta.color }]}>
            {story.story_type.replace(/_/g, ' ').toUpperCase()}
          </AppText>
          <AppText style={styles.storyTitle} numberOfLines={1}>
            {story.title}
          </AppText>
        </View>
        {story.metric_label ? (
          <View style={styles.metricGroup}>
            <AppText style={[styles.metricValue, { color: meta.color }]}>{story.metric_value}</AppText>
            <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
          </View>
        ) : null}
        {onPress ? <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} /> : null}
      </View>

      {isMatchup ? (
        <View style={styles.matchupRow}>
          <AppText style={styles.matchupTeam} numberOfLines={1}>
            {story.primary_team}
          </AppText>
          <AppText style={styles.matchupVs}>vs</AppText>
          <AppText style={[styles.matchupTeam, styles.matchupTeamMuted]} numberOfLines={1}>
            {story.secondary_team}
          </AppText>
        </View>
      ) : null}

      {isTrade && story.secondary_team ? (
        <View style={styles.tradeRow}>
          <View style={styles.tradeChip}>
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <Ionicons name="swap-horizontal" size={14} color={colors.textTertiary} />
          <View style={styles.tradeChip}>
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.secondary_team}
            </AppText>
          </View>
        </View>
      ) : null}

      <AppText style={styles.storySummary} numberOfLines={3}>
        {story.summary}
      </AppText>
      </TouchableOpacity>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  weekPickerRow: {
    flexGrow: 0,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  weekPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    marginRight: spacing.sm,
  },
  weekPillActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent },
  weekPillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  weekPillTextActive: { color: colors.accent },
  inlineLoadingRow: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  headerTextGroup: { flex: 1 },
  kicker: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.8, marginBottom: 4 },
  headline: { fontSize: 26, fontWeight: '700', color: colors.textPrimary },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    marginTop: 2,
  },
  shareButtonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  incompleteNotice: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: spacing.xl },
  storyCard: { marginBottom: spacing.sm },
  storyHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  storyTextGroup: { flex: 1 },
  storyKicker: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5, marginBottom: 2 },
  storyTitle: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  metricGroup: { alignItems: 'flex-end' },
  metricValue: { fontSize: 20, fontWeight: '700' },
  metricLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  matchupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  matchupTeam: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  matchupTeamMuted: { color: colors.textSecondary, fontWeight: '500' },
  matchupVs: { fontSize: 11, color: colors.textTertiary, fontWeight: '600' },
  tradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  tradeChip: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  tradeChipText: { fontSize: 12, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  storySummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}

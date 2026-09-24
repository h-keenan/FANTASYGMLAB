import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
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

// Per-story-type glyph/color — same semantic families used everywhere else
// (gold = achievement, red = rivalry/heat, green = value win, cyan =
// trade/GM activity, violet = league-wide activity). Two story types can
// share a category (see storyCategory below) while keeping a distinct icon.
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

/** Collapses the ten backend story types into the handful of categories a
 * user actually thinks in terms of — e.g. the week's top AND bottom scorer
 * both read as "Performance". Used only to group cards (Magna Carta §12);
 * the individual story_type still drives each row's own icon/summary. */
function storyCategory(storyType: string): string {
  if (storyType.startsWith('performance')) return 'performance';
  if (storyType.startsWith('matchup')) return 'matchup';
  if (storyType.startsWith('waiver')) return 'waiver';
  if (storyType === 'trade') return 'trade';
  if (storyType.startsWith('activity')) return 'activity';
  if (storyType === 'roster_riser') return 'roster';
  return 'other';
}

function categoryMeta(colors: ThemeColors): Record<
  string,
  { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }
> {
  return {
    performance: { label: 'Performance', icon: 'trophy-outline', color: colors.premium },
    matchup: { label: 'Matchups', icon: 'flame-outline', color: colors.danger },
    waiver: { label: 'Waivers', icon: 'cash-outline', color: colors.success },
    trade: { label: 'Trades', icon: 'swap-horizontal-outline', color: colors.accent },
    activity: { label: 'League Activity', icon: 'repeat-outline', color: colors.violet },
    roster: { label: 'Roster Watch', icon: 'trending-up-outline', color: colors.accent },
    other: { label: 'Storylines', icon: 'newspaper-outline', color: colors.textSecondary },
  };
}

interface StoryGroupData {
  category: string;
  stories: RecapStory[];
}

/** Merges consecutive same-category stories into one group, mirroring
 * AlertsScreen's adjacent-run grouping — backend story order (see
 * modules/league_recaps.py's builder list) stays intact, only genuinely
 * related storylines end up sharing one surface. */
function groupStories(stories: RecapStory[]): StoryGroupData[] {
  const groups: StoryGroupData[] = [];
  for (const story of stories) {
    const category = storyCategory(story.story_type);
    const last = groups[groups.length - 1];
    if (last && last.category === category) {
      last.stories.push(story);
    } else {
      groups.push({ category, stories: [story] });
    }
  }
  return groups;
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

  // Shared by the hero story and every grouped row below: trade stories open
  // the trade-detail modal (it already has full player_id asset lists),
  // everything else — every non-trade story type carries primary_roster_id,
  // see modules/league_recaps.py's `_story()` builder — navigates to that
  // team's roster the same way TeamsScreen/LeagueDetailScreen do.
  const resolveStoryPress = (story: RecapStory): (() => void) | undefined => {
    if (story.story_type === 'trade') {
      return () => setTradeStory(story);
    }
    if (story.primary_roster_id) {
      const rosterId = story.primary_roster_id;
      const rosterEntry = rosterMap[rosterId];
      return () =>
        navigation.navigate('TeamRoster', {
          ownerName: rosterEntry?.teamName || story.primary_team,
          playerIds: rosterEntry?.playerIds ?? [],
          leagueId,
          leagueName,
          rosterId,
        });
    }
    return undefined;
  };

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
        <EmptyState
          icon="newspaper-outline"
          title="Recap not ready yet"
          subtitle="Check back after this week's matchups finish scoring."
        />
      </View>
    );
  }

  const leadStory = recap.stories[0];
  const groupedStories = recap.incomplete ? [] : groupStories(recap.stories.slice(1));

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
        <EmptyState
          icon="newspaper-outline"
          title="Not enough data yet"
          subtitle={recap.empty_reason || 'Not enough historical data yet.'}
        />
      ) : (
        <>
          <LeadStoryCard story={leadStory} onPress={resolveStoryPress(leadStory)} />
          {groupedStories.map((group, index) => (
            <StoryGroup
              key={`${group.category}-${index}`}
              category={group.category}
              stories={group.stories}
              resolvePress={resolveStoryPress}
            />
          ))}
        </>
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

/**
 * The week's lead story — always `stories[0]` (see build_weekly_recap's
 * builder priority order, the same story the headline text above is derived
 * from) — rendered as one standout glowing card instead of blending into
 * the list below it (Magna Carta §12/§15: reserve glow for the one thing on
 * a screen that genuinely matters most).
 */
function LeadStoryCard({ story, onPress }: { story: RecapStory; onPress?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = storyMeta(colors)[story.story_type] ?? defaultStoryMeta(colors);
  const isMatchup = story.story_type === 'matchup' || story.story_type === 'matchup_close';
  const isTrade = story.story_type === 'trade';

  return (
    <AnimatedCard glow style={styles.leadCard} onPress={onPress}>
      <View style={styles.leadHeaderRow}>
        <IconCircle name={meta.icon} color={meta.color} size={48} iconSize={22} />
        <View style={styles.storyTextGroup}>
          <AppText style={[styles.leadKicker, { color: meta.color }]}>
            {story.story_type.replace(/_/g, ' ').toUpperCase()}
          </AppText>
          <AppText style={styles.leadTitle}>{story.title}</AppText>
        </View>
        {story.metric_label ? (
          <View style={styles.metricGroup}>
            <AppText style={[styles.leadMetricValue, { color: meta.color }]}>{story.metric_value}</AppText>
            <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
          </View>
        ) : null}
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

      <AppText style={styles.leadSummary}>{story.summary}</AppText>

      {onPress ? (
        <View style={styles.leadFooterRow}>
          <AppText style={[styles.leadFooterText, { color: meta.color }]}>
            {isTrade ? 'View trade details' : 'View team'}
          </AppText>
          <Ionicons name="chevron-forward" size={14} color={meta.color} />
        </View>
      ) : null}
    </AnimatedCard>
  );
}

/** One grouped surface per category (Performance, Matchups, Waivers, ...)
 * containing every remaining story of that kind as compact rows separated
 * by dividers, instead of each story repeating as its own identically
 * bordered card (Magna Carta §12). */
function StoryGroup({
  category,
  stories,
  resolvePress,
}: {
  category: string;
  stories: RecapStory[];
  resolvePress: (story: RecapStory) => (() => void) | undefined;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = categoryMeta(colors)[category] ?? categoryMeta(colors).other;

  return (
    <View style={styles.group}>
      <View style={styles.groupHeaderRow}>
        <View style={[styles.groupAccentBar, { backgroundColor: meta.color }]} />
        <Ionicons name={meta.icon} size={13} color={meta.color} style={styles.groupIcon} />
        <AppText style={[styles.groupLabel, { color: meta.color }]} numberOfLines={1}>
          {meta.label}
        </AppText>
      </View>
      <AnimatedCard style={styles.groupCard}>
        {stories.map((story, index) => (
          <StoryRow
            key={`${story.story_type}-${index}`}
            story={story}
            showDivider={index < stories.length - 1}
            onPress={resolvePress(story)}
          />
        ))}
      </AnimatedCard>
    </View>
  );
}

function StoryRow({ story, showDivider, onPress }: { story: RecapStory; showDivider: boolean; onPress?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = storyMeta(colors)[story.story_type] ?? defaultStoryMeta(colors);
  const isMatchup = story.story_type === 'matchup' || story.story_type === 'matchup_close';
  const isTrade = story.story_type === 'trade';

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.rowDivider]}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.7}
    >
      <View style={styles.rowHeaderRow}>
        <IconCircle name={meta.icon} color={meta.color} size={32} iconSize={15} />
        <AppText style={styles.rowTitle} numberOfLines={1}>
          {story.title}
        </AppText>
        {story.metric_label ? (
          <View style={styles.metricGroup}>
            <AppText style={[styles.metricValue, { color: meta.color }]}>{story.metric_value}</AppText>
            <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
          </View>
        ) : null}
        {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
      </View>

      {isMatchup ? (
        <View style={styles.matchupRowCompact}>
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
        <View style={styles.tradeRowCompact}>
          <View style={styles.tradeChip}>
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <Ionicons name="swap-horizontal" size={13} color={colors.textTertiary} />
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
  storyTextGroup: { flex: 1 },
  metricGroup: { alignItems: 'flex-end' },
  metricValue: { fontSize: 18, fontWeight: '700' },
  metricLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  matchupTeam: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  matchupTeamMuted: { color: colors.textSecondary, fontWeight: '500' },
  matchupVs: { fontSize: 11, color: colors.textTertiary, fontWeight: '600' },
  tradeChip: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  tradeChipText: { fontSize: 12, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  storySummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  error: { color: colors.danger, textAlign: 'center' },

  // Lead story (hero) card — bigger type + glow, the one card on this screen
  // allowed to visually dominate (Magna Carta §15).
  leadCard: { marginBottom: spacing.lg },
  leadHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  leadKicker: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6, marginBottom: 3 },
  leadTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  leadMetricValue: { fontSize: 24, fontWeight: '800' },
  matchupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  tradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  leadSummary: { fontSize: 14, color: colors.textSecondary, lineHeight: 20, marginTop: spacing.md },
  leadFooterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  leadFooterText: { fontSize: 12, fontWeight: '700' },

  // Grouped-story surfaces below the hero — one AnimatedCard per category
  // with internal dividers between rows (Magna Carta §12).
  group: { marginBottom: spacing.md },
  groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
  groupAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
  groupIcon: { marginLeft: -2 },
  groupLabel: { flex: 1, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
  row: { paddingVertical: spacing.sm + 2 },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  rowTitle: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  matchupRowCompact: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  tradeRowCompact: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  });
}

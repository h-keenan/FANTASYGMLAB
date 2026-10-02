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
import TeamAvatar from '../components/TeamAvatar';
import { api, type RecapStory, type WeeklyRecap } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
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

export type RosterMap = Record<string, { playerIds: string[]; teamName: string; avatarId: string }>;

/** Sleeper avatar id for a story's team, when its roster_id resolved against
 * `rosterMap` — `TeamAvatar` already renders a graceful empty-circle
 * fallback for '' / undefined, so a miss here never blocks rendering. */
function avatarFor(rosterMap: RosterMap, rosterId: string | undefined): string | undefined {
  if (!rosterId) return undefined;
  return rosterMap[rosterId]?.avatarId || undefined;
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
  const [rosterMap, setRosterMap] = useState<RosterMap>({});

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
        if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load recap.'));
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
        const map: RosterMap = {};
        for (const roster of rostersResult.rosters) {
          const rosterId = String(roster.roster_id ?? '');
          if (!rosterId) continue;
          const players = Array.isArray(roster.players) ? roster.players : [];
          map[rosterId] = {
            playerIds: players.map(String),
            teamName: profilesResult.profiles[rosterId]?.team_name || '',
            avatarId: profilesResult.profiles[rosterId]?.avatar_id || '',
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
          <LeadStoryCard story={leadStory} onPress={resolveStoryPress(leadStory)} rosterMap={rosterMap} />
          {groupedStories.map((group, index) => (
            <StoryGroup
              key={`${group.category}-${index}`}
              category={group.category}
              stories={group.stories}
              resolvePress={resolveStoryPress}
              rosterMap={rosterMap}
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
        rosterMap={rosterMap}
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
 *
 * The AnimatedCard's cyan glow rim stays the universal "this is the hero"
 * signal used app-wide (Dashboard/GmPlan/Alerts/Matchup/Waiver all glow the
 * same color) — per-category *content* inside the card (icon ring, avatar
 * ring, tinted header panel, headline number) carries the story's own
 * semantic color instead, so the hero still reads as distinct per category
 * without redefining what "glow" means globally.
 */
function LeadStoryCard({
  story,
  onPress,
  rosterMap,
}: {
  story: RecapStory;
  onPress?: () => void;
  rosterMap: RosterMap;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = storyMeta(colors)[story.story_type] ?? defaultStoryMeta(colors);
  const isMatchup = story.story_type === 'matchup' || story.story_type === 'matchup_close';
  const isTrade = story.story_type === 'trade';
  // Matchup's own scoreboard below already gives the margin number a huge,
  // centered focal point — showing it a second time in the header's
  // top-right metric slot would just be noise competing with itself.
  const showHeaderMetric = Boolean(story.metric_label) && !isMatchup;

  return (
    <AnimatedCard glow style={styles.leadCard} onPress={onPress}>
      <View style={[styles.leadTintPanel, { backgroundColor: `${meta.color}17` }]}>
        <View style={styles.leadHeaderRow}>
          <IconCircle
            name={meta.icon}
            color={meta.color}
            size={52}
            iconSize={24}
            style={[styles.ringedIcon, { borderColor: meta.color }]}
          />
          {!isMatchup && !isTrade ? (
            <TeamAvatar
              avatarId={avatarFor(rosterMap, story.primary_roster_id)}
              size={44}
              style={[styles.avatarRing, { borderColor: meta.color }]}
            />
          ) : null}
          <View style={styles.storyTextGroup}>
            <AppText style={[styles.leadKicker, { color: meta.color }]}>
              {story.story_type.replace(/_/g, ' ').toUpperCase()}
            </AppText>
            <AppText style={styles.leadTitle}>{story.title}</AppText>
          </View>
          {showHeaderMetric ? (
            <View style={styles.metricGroup}>
              <AppText style={[styles.leadMetricValue, { color: meta.color }]}>{story.metric_value}</AppText>
              <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
            </View>
          ) : null}
        </View>

        {isMatchup ? (
          <View style={styles.scoreboardRow}>
            <View style={styles.scoreboardTeam}>
              <TeamAvatar
                avatarId={avatarFor(rosterMap, story.primary_roster_id)}
                size={56}
                style={[styles.avatarRing, { borderColor: meta.color }]}
              />
              <AppText style={styles.scoreboardTeamName} numberOfLines={1}>
                {story.primary_team}
              </AppText>
            </View>
            <View style={styles.scoreboardMetric}>
              <AppText style={[styles.scoreboardValue, { color: meta.color }]} numberOfLines={1}>
                {story.metric_value}
              </AppText>
              <AppText style={styles.metricLabel}>{(story.metric_label || '').toUpperCase()}</AppText>
            </View>
            <View style={styles.scoreboardTeam}>
              <TeamAvatar
                avatarId={avatarFor(rosterMap, story.secondary_roster_id)}
                size={56}
                style={styles.avatarMuted}
              />
              <AppText style={[styles.scoreboardTeamName, styles.scoreboardTeamMuted]} numberOfLines={1}>
                {story.secondary_team}
              </AppText>
            </View>
          </View>
        ) : null}

        {isTrade && story.secondary_team ? (
          <View style={styles.tradeRow}>
            <View style={styles.tradeChip}>
              <TeamAvatar avatarId={avatarFor(rosterMap, story.primary_roster_id)} size={24} />
              <AppText style={styles.tradeChipText} numberOfLines={1}>
                {story.primary_team}
              </AppText>
            </View>
            <Ionicons name="swap-horizontal" size={14} color={colors.textTertiary} />
            <View style={styles.tradeChip}>
              <TeamAvatar avatarId={avatarFor(rosterMap, story.secondary_roster_id)} size={24} />
              <AppText style={styles.tradeChipText} numberOfLines={1}>
                {story.secondary_team}
              </AppText>
            </View>
          </View>
        ) : null}
      </View>

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
  rosterMap,
}: {
  category: string;
  stories: RecapStory[];
  resolvePress: (story: RecapStory) => (() => void) | undefined;
  rosterMap: RosterMap;
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
        {stories.map((story, index) =>
          index === 0 ? (
            <FeaturedStoryRow
              key={`${story.story_type}-${index}`}
              story={story}
              showDivider={index < stories.length - 1}
              onPress={resolvePress(story)}
              rosterMap={rosterMap}
              meta={meta}
            />
          ) : (
            <StoryRow
              key={`${story.story_type}-${index}`}
              story={story}
              showDivider={index < stories.length - 1}
              onPress={resolvePress(story)}
              rosterMap={rosterMap}
            />
          ),
        )}
      </AnimatedCard>
    </View>
  );
}

/**
 * The most significant story within its category — always the first story
 * of a given category in `recap.stories` (backend emits each category's
 * headline-worthy builder before its "opposite extreme"/routine counterpart,
 * e.g. the week's highest FAAB win before the cheapest waiver add; see
 * build_weekly_recap's builder order in modules/league_recaps.py). Gets a
 * category-tinted background, a thicker colored avatar/icon ring, and a
 * genuinely larger headline number — the second tier of this screen's
 * three-tier hierarchy (hero card → featured row → routine row), so a
 * category's one real storyline doesn't carry the same visual weight as its
 * routine counterpart directly beneath it.
 */
function FeaturedStoryRow({
  story,
  showDivider,
  onPress,
  rosterMap,
  meta,
}: {
  story: RecapStory;
  showDivider: boolean;
  onPress?: () => void;
  rosterMap: RosterMap;
  meta: { icon: React.ComponentProps<typeof Ionicons>['name']; color: string };
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isMatchup = story.story_type === 'matchup' || story.story_type === 'matchup_close';
  const isTrade = story.story_type === 'trade';
  const showMetric = Boolean(story.metric_label) && !isMatchup;

  return (
    <TouchableOpacity
      style={[styles.featuredRow, { backgroundColor: `${meta.color}14` }, showDivider && styles.rowDivider]}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.7}
    >
      <View style={styles.rowHeaderRow}>
        <IconCircle
          name={meta.icon}
          color={meta.color}
          size={40}
          iconSize={19}
          style={[styles.ringedIconThin, { borderColor: meta.color }]}
        />
        {!isMatchup && !isTrade ? (
          <TeamAvatar
            avatarId={avatarFor(rosterMap, story.primary_roster_id)}
            size={36}
            style={[styles.avatarRingThin, { borderColor: meta.color }]}
          />
        ) : null}
        <AppText style={styles.featuredTitle} numberOfLines={1}>
          {story.title}
        </AppText>
        {showMetric ? (
          <View style={styles.metricGroup}>
            <AppText style={[styles.featuredMetricValue, { color: meta.color }]}>{story.metric_value}</AppText>
            <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
          </View>
        ) : null}
        {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
      </View>

      {isMatchup ? (
        <View style={styles.scoreboardRowCompact}>
          <View style={styles.scoreboardTeam}>
            <TeamAvatar
              avatarId={avatarFor(rosterMap, story.primary_roster_id)}
              size={38}
              style={[styles.avatarRingThin, { borderColor: meta.color }]}
            />
            <AppText style={styles.matchupTeam} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <AppText style={[styles.scoreboardValueCompact, { color: meta.color }]} numberOfLines={1}>
            {story.metric_value}
          </AppText>
          <View style={styles.scoreboardTeam}>
            <TeamAvatar
              avatarId={avatarFor(rosterMap, story.secondary_roster_id)}
              size={38}
              style={styles.avatarMuted}
            />
            <AppText style={[styles.matchupTeam, styles.matchupTeamMuted]} numberOfLines={1}>
              {story.secondary_team}
            </AppText>
          </View>
        </View>
      ) : null}

      {isTrade && story.secondary_team ? (
        <View style={styles.tradeRowCompact}>
          <View style={styles.tradeChip}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.primary_roster_id)} size={22} />
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <Ionicons name="swap-horizontal" size={13} color={colors.textTertiary} />
          <View style={styles.tradeChip}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.secondary_roster_id)} size={22} />
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.secondary_team}
            </AppText>
          </View>
        </View>
      ) : null}

      <AppText style={styles.featuredSummary}>{story.summary}</AppText>
    </TouchableOpacity>
  );
}

/**
 * Every other story in a category — a routine FAAB add, a quiet week, the
 * close-but-not-the-headline matchup. Deliberately quieter than
 * `FeaturedStoryRow` above it: a smaller neutral-ring icon, a secondary-tone
 * (not category-color) metric number, and a tighter two-line summary clamp
 * — real information, just not fighting the featured row for attention
 * (coridian_'s "$0 FAAB pickup shouldn't read as dramatic as a blowout").
 */
function StoryRow({
  story,
  showDivider,
  onPress,
  rosterMap,
}: {
  story: RecapStory;
  showDivider: boolean;
  onPress?: () => void;
  rosterMap: RosterMap;
}) {
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
        <IconCircle name={meta.icon} color={meta.color} size={28} iconSize={13} />
        {!isMatchup && !isTrade ? (
          <TeamAvatar avatarId={avatarFor(rosterMap, story.primary_roster_id)} size={26} />
        ) : null}
        <AppText style={styles.rowTitle} numberOfLines={1}>
          {story.title}
        </AppText>
        {story.metric_label ? (
          <View style={styles.metricGroup}>
            <AppText style={styles.metricValue}>{story.metric_value}</AppText>
            <AppText style={styles.metricLabel}>{story.metric_label.toUpperCase()}</AppText>
          </View>
        ) : null}
        {onPress ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
      </View>

      {isMatchup ? (
        <View style={styles.matchupRowCompact}>
          <View style={styles.matchupTeamGroup}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.primary_roster_id)} size={22} />
            <AppText style={styles.matchupTeam} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <AppText style={styles.matchupVs}>vs</AppText>
          <View style={styles.matchupTeamGroup}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.secondary_roster_id)} size={22} />
            <AppText style={[styles.matchupTeam, styles.matchupTeamMuted]} numberOfLines={1}>
              {story.secondary_team}
            </AppText>
          </View>
        </View>
      ) : null}

      {isTrade && story.secondary_team ? (
        <View style={styles.tradeRowCompact}>
          <View style={styles.tradeChip}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.primary_roster_id)} size={18} />
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.primary_team}
            </AppText>
          </View>
          <Ionicons name="swap-horizontal" size={13} color={colors.textTertiary} />
          <View style={styles.tradeChip}>
            <TeamAvatar avatarId={avatarFor(rosterMap, story.secondary_roster_id)} size={18} />
            <AppText style={styles.tradeChipText} numberOfLines={1}>
              {story.secondary_team}
            </AppText>
          </View>
        </View>
      ) : null}

      <AppText style={styles.storySummary} numberOfLines={2}>
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
  // Routine-row metric: deliberately plain textSecondary, not the category
  // color — a $0 FAAB add shouldn't visually compete with the featured
  // row's bold colored number directly above it in the same group.
  metricValue: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  metricLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  matchupTeamGroup: { flex: 1, alignItems: 'center', gap: 4 },
  matchupTeam: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  matchupTeamMuted: { color: colors.textSecondary, fontWeight: '500' },
  matchupVs: { fontSize: 11, color: colors.textTertiary, fontWeight: '600' },
  // Colored rings — a bolder presence than a flat icon/avatar, scaled down
  // for the featured tier vs. the hero tier (Magna Carta §19/§20: one
  // player/team-identity visual language, varied through size/weight only).
  ringedIcon: { borderWidth: 2 },
  ringedIconThin: { borderWidth: 1.5 },
  avatarRing: { borderWidth: 2 },
  avatarRingThin: { borderWidth: 1.5 },
  avatarMuted: { opacity: 0.55 },
  tradeChip: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  tradeChipText: { flex: 1, fontSize: 12, fontWeight: '600', color: colors.textPrimary },
  error: { color: colors.danger, textAlign: 'center' },

  // Lead story (hero) card — bigger type + glow, the one card on this screen
  // allowed to visually dominate (Magna Carta §15).
  leadCard: { marginBottom: spacing.lg },
  // Category-tinted banner bleeding to the card's own edges (AnimatedCard's
  // default padding is spacing.lg, so a matching negative margin + re-applied
  // padding recreates the inset while the tint paints behind it). Square
  // corners (radii.md === 0 app-wide) mean no corner-radius matching is
  // needed for the bleed to look intentional rather than clipped.
  leadTintPanel: {
    marginTop: -spacing.lg,
    marginHorizontal: -spacing.lg,
    paddingTop: spacing.lg,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    marginBottom: spacing.md,
  },
  leadHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  leadKicker: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6, marginBottom: 3 },
  leadTitle: { fontSize: 18, fontWeight: '700', color: colors.textPrimary },
  // Bumped from 24->30 — the one number on this screen allowed to read as a
  // genuine headline stat rather than a label-adjacent figure (Magna Carta
  // §10's "display/hero" tier, reserved here for the single most dramatic
  // story on the whole screen).
  leadMetricValue: { fontSize: 30, fontWeight: '800', letterSpacing: -0.5 },
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

  // Hero-tier matchup "scoreboard": two team avatars flanking one giant
  // centered margin number — the number genuinely IS the story here, so it
  // gets the biggest type on the whole screen instead of competing with the
  // teams' names at equal weight (coridian_'s core complaint).
  scoreboardRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  scoreboardTeam: { flex: 1, alignItems: 'center', gap: spacing.xs },
  scoreboardTeamName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  scoreboardTeamMuted: { color: colors.textSecondary, fontWeight: '500' },
  scoreboardMetric: { alignItems: 'center', paddingHorizontal: spacing.xs },
  scoreboardValue: { fontSize: 38, fontWeight: '800', letterSpacing: -1 },
  // Featured-tier (in-group) scoreboard — same idea, smaller.
  scoreboardRowCompact: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  scoreboardValueCompact: { fontSize: 22, fontWeight: '800', letterSpacing: -0.5 },

  // Grouped-story surfaces below the hero — one AnimatedCard per category
  // with internal dividers between rows (Magna Carta §12). The card itself
  // carries no padding so each row (featured or routine) can supply its own
  // horizontal inset — required for the featured row's tint to bleed flush
  // to the card's edges.
  group: { marginBottom: spacing.md },
  groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
  groupAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
  groupIcon: { marginLeft: -2 },
  groupLabel: { flex: 1, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  groupCard: { padding: 0 },
  // Featured row (tier 2) — the category's one real storyline: tinted
  // background, thicker colored rings, a larger bolded number, full summary.
  featuredRow: { paddingHorizontal: spacing.md, paddingVertical: spacing.md },
  featuredTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  featuredMetricValue: { fontSize: 20, fontWeight: '800' },
  featuredSummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  // Routine row (tier 3) — everything else in the category: quieter type,
  // neutral metric color, tighter summary clamp (coridian_'s "$0 FAAB
  // pickup" example shouldn't fight the featured row above it for attention).
  row: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  rowTitle: { flex: 1, fontSize: 13, fontWeight: '500', color: colors.textSecondary },
  matchupRowCompact: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  tradeRowCompact: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  storySummary: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginTop: spacing.xs },
  });
}

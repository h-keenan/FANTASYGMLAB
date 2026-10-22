import React, { forwardRef } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';
import TeamAvatar from './TeamAvatar';
import ShareCardChrome, { CARD_WIDTH } from './ShareCardChrome';
import { Ionicons } from '@expo/vector-icons';

import type { RecapStory, WeeklyRecap } from '../lib/api';
import { colors, radii, spacing } from '../theme';

const CARD_HEIGHT = 520;
const MAX_STORIES = 3;

/** Minimal roster-id -> avatar lookup the share card needs — structurally
 * compatible with RecapScreen's richer RosterMap (playerIds/teamName are
 * simply ignored here). */
export type RecapRosterMap = Record<string, { avatarId?: string }>;

const STORY_META: Record<string, { icon: React.ComponentProps<typeof Ionicons>['name']; color: string }> = {
  performance: { icon: 'trophy', color: colors.premium },
  matchup: { icon: 'flame', color: colors.danger },
  waiver: { icon: 'cash-outline', color: colors.success },
  trade: { icon: 'swap-horizontal', color: colors.accent },
  activity: { icon: 'repeat', color: colors.violet },
  roster_riser: { icon: 'trending-up', color: colors.accent },
};
const DEFAULT_STORY_META = { icon: 'newspaper-outline' as const, color: colors.textSecondary };

// Only single-team story types get a team avatar in place of the generic
// icon disc — matchup/trade involve two teams and this compact one-line
// layout has no room to show both without a larger restructure (see
// RecapShareCard's usage note below).
const SINGLE_TEAM_TYPES = new Set([
  'performance',
  'performance_low',
  'waiver',
  'waiver_low',
  'activity',
  'activity_low',
  'roster_riser',
]);

function StoryLine({ story, rosterMap }: { story: RecapStory; rosterMap: RecapRosterMap }) {
  const meta = STORY_META[story.story_type] ?? DEFAULT_STORY_META;
  const avatarId = SINGLE_TEAM_TYPES.has(story.story_type) ? rosterMap[story.primary_roster_id]?.avatarId : undefined;
  return (
    <View style={styles.storyLine}>
      {avatarId ? (
        <TeamAvatar avatarId={avatarId} size={32} />
      ) : (
        <View style={[styles.storyIconDisc, { backgroundColor: `${meta.color}26` }]}>
          <Ionicons name={meta.icon} size={14} color={meta.color} />
        </View>
      )}
      <View style={styles.storyTextGroup}>
        <AppText style={styles.storyTitle} numberOfLines={1}>
          {story.title}
        </AppText>
        {story.metric_value ? (
          <AppText style={[styles.storyMetric, { color: meta.color }]} numberOfLines={1}>
            {story.metric_value}
            {story.metric_label ? ` ${story.metric_label}` : ''}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

/**
 * Shareable branded PNG for a weekly League Recap — same wireframe treatment
 * as TradeShareCard (logo/wordmark header, hairline dividers, "SCAN TO TRY"
 * QR footer), built from the same WeeklyRecap data the on-screen Recap
 * screen shows. Fixed 360x500 logical size for consistent capture.
 */
const RecapShareCard = forwardRef<View, { leagueName: string; recap: WeeklyRecap; rosterMap: RecapRosterMap }>(
  ({ leagueName, recap, rosterMap }, ref) => {
    const stories = recap.stories.slice(0, MAX_STORIES);
    return (
      <ShareCardChrome
        ref={ref}
        kind="League Recap"
        height={CARD_HEIGHT}
        headerRight={
          <AppText style={styles.leagueName} numberOfLines={1}>
            {leagueName.toUpperCase()}
          </AppText>
        }
      >
        <AppText style={styles.kicker}>LEAGUE MEMORY · WEEK {recap.week}</AppText>
        <AppText style={styles.headline}>{recap.headline}</AppText>

        <View style={styles.hairline} />

        <View style={styles.storiesGroup}>
          {stories.map((story, index) => (
            <StoryLine key={`${story.story_type}-${index}`} story={story} rosterMap={rosterMap} />
          ))}
        </View>

      </ShareCardChrome>
    );
  },
);
RecapShareCard.displayName = 'RecapShareCard';

export default RecapShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  leagueName: { fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.6, maxWidth: 120 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  kicker: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.8, marginTop: spacing.xs },
  headline: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, marginTop: 4 },
  storiesGroup: { gap: spacing.md, marginTop: spacing.xs },
  storyLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  storyIconDisc: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  storyTextGroup: { flex: 1 },
  storyTitle: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  storyMetric: { fontSize: 11, fontWeight: '700', marginTop: 1 },
});

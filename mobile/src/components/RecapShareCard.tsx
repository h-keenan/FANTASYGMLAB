import React, { forwardRef } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import QRCode from 'react-native-qrcode-svg';

import type { RecapStory, WeeklyRecap } from '../lib/api';
import { colors, radii, spacing } from '../theme';

const CARD_WIDTH = 360;
const CARD_HEIGHT = 500;
const SHARE_QR_URL = 'https://fantasygmlab.com';
const QR_SIZE = 60;
const MAX_STORIES = 3;

const STORY_META: Record<string, { icon: React.ComponentProps<typeof Ionicons>['name']; color: string }> = {
  performance: { icon: 'trophy', color: colors.premium },
  matchup: { icon: 'flame', color: colors.danger },
  waiver: { icon: 'cash-outline', color: colors.success },
  trade: { icon: 'swap-horizontal', color: colors.accent },
  activity: { icon: 'repeat', color: colors.violet },
  roster_riser: { icon: 'trending-up', color: colors.accent },
};
const DEFAULT_STORY_META = { icon: 'newspaper-outline' as const, color: colors.textSecondary };

function StoryLine({ story }: { story: RecapStory }) {
  const meta = STORY_META[story.story_type] ?? DEFAULT_STORY_META;
  return (
    <View style={styles.storyLine}>
      <View style={[styles.storyIconDisc, { backgroundColor: `${meta.color}26` }]}>
        <Ionicons name={meta.icon} size={14} color={meta.color} />
      </View>
      <View style={styles.storyTextGroup}>
        <Text style={styles.storyTitle} numberOfLines={1}>
          {story.title}
        </Text>
        {story.metric_value ? (
          <Text style={[styles.storyMetric, { color: meta.color }]} numberOfLines={1}>
            {story.metric_value}
            {story.metric_label ? ` ${story.metric_label}` : ''}
          </Text>
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
const RecapShareCard = forwardRef<View, { leagueName: string; recap: WeeklyRecap }>(
  ({ leagueName, recap }, ref) => {
    const stories = recap.stories.slice(0, MAX_STORIES);
    return (
      <View ref={ref} collapsable={false} style={styles.card}>
        <View style={styles.headerRow}>
          <View style={styles.brandRow}>
            <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
            <Text style={styles.brandWord}>
              FANTASY<Text style={styles.brandWordAccent}>GM</Text> LAB
            </Text>
          </View>
          <Text style={styles.leagueName} numberOfLines={1}>
            {leagueName.toUpperCase()}
          </Text>
        </View>

        <View style={styles.hairline} />

        <Text style={styles.kicker}>LEAGUE MEMORY · WEEK {recap.week}</Text>
        <Text style={styles.headline}>{recap.headline}</Text>

        <View style={styles.hairline} />

        <View style={styles.storiesGroup}>
          {stories.map((story, index) => (
            <StoryLine key={`${story.story_type}-${index}`} story={story} />
          ))}
        </View>

        <View style={styles.qrRow}>
          <View style={styles.qrTextGroup}>
            <Text style={styles.qrKicker}>SCAN TO TRY</Text>
            <Text style={styles.qrTitle}>FantasyGM Lab</Text>
            <Text style={styles.qrSubtitle}>Real trade grades, waiver signal, and a Trade Hub built for dynasty.</Text>
          </View>
          <View style={styles.qrWrap}>
            <QRCode
              value={SHARE_QR_URL}
              size={QR_SIZE}
              color={colors.background}
              backgroundColor="#fff"
              logo={require('../../assets/icon.png')}
              logoSize={QR_SIZE * 0.28}
              logoBorderRadius={4}
              logoBackgroundColor="#fff"
              ecl="H"
            />
          </View>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            <Text style={{ color: colors.accent }}>PLAN. </Text>
            <Text style={{ color: colors.premium }}>PROJECT. </Text>
            <Text style={{ color: colors.danger }}>WIN.</Text>
          </Text>
        </View>
      </View>
    );
  },
);
RecapShareCard.displayName = 'RecapShareCard';

export default RecapShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    backgroundColor: colors.background,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  brandMark: { width: 28, height: 28, borderRadius: 8 },
  brandWord: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, letterSpacing: 0.5 },
  brandWordAccent: { color: colors.accent },
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
  qrRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    gap: spacing.md,
  },
  qrTextGroup: { flex: 1 },
  qrKicker: { fontSize: 9, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
  qrTitle: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
  qrSubtitle: { fontSize: 10, color: colors.textSecondary, lineHeight: 13, marginTop: 2 },
  qrWrap: {
    padding: 6,
    backgroundColor: '#fff',
    borderRadius: radii.sm,
  },
  footer: { position: 'absolute', bottom: spacing.md, left: 0, right: 0, alignItems: 'center' },
  footerText: { fontSize: 12, fontWeight: '700', letterSpacing: 1.5 },
});

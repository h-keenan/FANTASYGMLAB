import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import InsightRow from './InsightRow';
import PremiumLock from './PremiumLock';
import SkeletonBlock from './SkeletonBlock';
import { api } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { setLastLeague } from '../lib/lastLeague';
import {
  glanceDestination,
  glanceFailedNote,
  glanceLayout,
  glanceNewsBadge,
  glanceRecordParts,
  glanceWaiverHeadline,
  type GlanceLayout,
  type GlanceModule,
  type GlanceSectionState,
  type LeagueGlance,
  type LeaguesGlanceResponse,
} from '../lib/leaguesGlance';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Navigation = NativeStackNavigationProp<RootStackParamList>;

/**
 * "All leagues at a glance" on the My Leagues screen: one compact card per
 * saved league with exactly five modules (record, top waiver add, top trade
 * idea, news/injury badge, top team need), each tapping straight into that
 * league's own feature screen.
 *
 * Deliberate, scoped exception to UI_HIERARCHY_DIRECTIVE.md §6 ("one
 * dominant module per screen"): the question this section answers is "how
 * are all my leagues doing", which is inherently a side-by-side comparison.
 * The exception lives here only; do not generalize it to other screens.
 *
 * Built from shared primitives: InsightRow (§28) for the waiver/trade/need
 * modules, PremiumLock for the Free teaser, SkeletonBlock for loading, and
 * the same surface/cardBorder/pill tokens HomeScreen's league rows use.
 */
export default function LeaguesGlanceSection({
  state,
  reloadToken,
  upsellFallback,
}: {
  state: GlanceSectionState;
  /** Bumped by the parent on focus/pull-to-refresh to re-read the (server
   * cached) cards. */
  reloadToken: number;
  upsellFallback?: { title: string; body: string };
}) {
  const navigation = useNavigation<Navigation>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [data, setData] = useState<LeaguesGlanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (state !== 'active') return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getLeaguesGlance()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(toUserErrorMessage(err, "Couldn't load your league overview."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [state, reloadToken]);

  const openModule = useCallback(
    (league: LeagueGlance, module: GlanceModule) => {
      const leagueName = league.league_name || 'League';
      void setLastLeague({ leagueId: league.league_id, leagueName });
      const destination = glanceDestination(module);
      const params = { leagueId: league.league_id, leagueName };
      switch (destination.screen) {
        case 'Trades':
          navigation.navigate('Trades', { ...params, initialTab: destination.initialTab });
          return;
        case 'Waivers':
          navigation.navigate('Waivers', params);
          return;
        case 'Alerts':
          navigation.navigate('Alerts', params);
          return;
        case 'MyTeam':
          navigation.navigate('MyTeam', params);
          return;
        default:
          navigation.navigate('Dashboard', params);
      }
    },
    [navigation],
  );

  if (state === 'hidden') return null;

  if (state === 'locked') {
    const upsell = upsellFallback ?? {
      title: 'All your leagues at a glance',
      body: "Premium keeps every league you're in and shows each one's record, top add, trade idea, news, and biggest need side by side.",
    };
    return (
      <View style={styles.section}>
        <SectionTitle styles={styles} />
        {/* Greyed structural preview only (no invented data): the real
            card layout with placeholder bars, under the shared lock. */}
        <View style={styles.teaser} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <View style={styles.grid}>
            <TeaserCard styles={styles} />
            <TeaserCard styles={styles} />
          </View>
        </View>
        <PremiumLock title={upsell.title} description={upsell.body} />
      </View>
    );
  }

  const cards = data?.leagues ?? [];
  const layout = glanceLayout(cards.length);
  const failedNote = glanceFailedNote(data?.failed_leagues ?? []);

  return (
    <View style={styles.section}>
      <SectionTitle styles={styles} />
      {loading && !data ? (
        <View style={styles.grid}>
          <SkeletonCard styles={styles} />
          <SkeletonCard styles={styles} />
        </View>
      ) : error && !data ? (
        <AppText style={styles.errorText}>{`${error} Pull down to retry.`}</AppText>
      ) : (
        <>
          <View style={layout === 'grid' ? styles.grid : styles.stack} testID={`leagues-glance-${layout}`}>
            {cards.map((league) => (
              <GlanceCard
                key={league.league_id}
                league={league}
                layout={layout}
                colors={colors}
                styles={styles}
                onOpen={openModule}
              />
            ))}
          </View>
          {failedNote ? (
            <View style={styles.failedNote}>
              <Ionicons name="alert-circle-outline" size={14} color={colors.textSecondary} />
              <AppText style={styles.failedNoteText}>{failedNote}</AppText>
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function SectionTitle({ styles }: { styles: ReturnType<typeof createStyles> }) {
  return <AppText style={styles.sectionTitle}>All leagues at a glance</AppText>;
}

function GlanceCard({
  league,
  layout,
  colors,
  styles,
  onOpen,
}: {
  league: LeagueGlance;
  layout: GlanceLayout;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onOpen: (league: LeagueGlance, module: GlanceModule) => void;
}) {
  const compact = layout === 'grid';
  const { record, rank } = glanceRecordParts(league.record);
  const badge = glanceNewsBadge(league.news);
  const badgeColor = badge.tone === 'risk' ? colors.danger : colors.textSecondary;
  const rows: Array<React.ComponentProps<typeof InsightRow> & { key: string }> = [];
  if (league.waiver) {
    rows.push({
      key: 'waiver',
      icon: 'person-add-outline',
      color: colors.success,
      label: 'Top add',
      headline: compact ? league.waiver.name : glanceWaiverHeadline(league.waiver),
      detail: compact ? null : league.waiver.reason,
      onPress: () => onOpen(league, 'waiver'),
    });
  }
  if (league.trade) {
    rows.push({
      key: 'trade',
      icon: 'swap-horizontal-outline',
      color: colors.accent,
      label: 'Trade idea',
      headline: league.trade.headline,
      detail: compact || !league.trade.partner_team_name ? null : `With ${league.trade.partner_team_name}`,
      onPress: () => onOpen(league, 'trade'),
    });
  }
  if (league.need) {
    rows.push({
      key: 'need',
      icon: 'construct-outline',
      color: league.need.category === 'injury_pressure' ? colors.danger : colors.premium,
      label: league.need.label || 'Team need',
      headline: league.need.value,
      onPress: () => onOpen(league, 'need'),
    });
  }

  return (
    <View style={[styles.card, compact && styles.cardCompact]}>
      <View style={styles.cardHeader}>
        <TouchableOpacity
          style={styles.identity}
          activeOpacity={0.7}
          onPress={() => onOpen(league, 'record')}
          accessibilityRole="button"
          accessibilityLabel={`Open ${league.league_name} dashboard`}
        >
          <AppText style={styles.leagueName} numberOfLines={1}>
            {league.league_name}
          </AppText>
          {league.team_name ? (
            <AppText style={styles.teamName} numberOfLines={1}>
              {league.team_name}
            </AppText>
          ) : null}
          {record ? (
            <View style={styles.recordRow}>
              <AppText style={styles.recordValue}>{record}</AppText>
              {rank ? <AppText style={styles.recordMeta}>{rank}</AppText> : null}
            </View>
          ) : null}
          {league.record?.playoff_status ? (
            <AppText style={styles.playoffStatus} numberOfLines={1}>
              {league.record.playoff_status}
            </AppText>
          ) : null}
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.newsBadge, { backgroundColor: `${badgeColor}1F` }]}
          onPress={() => onOpen(league, 'news')}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={badge.accessibilityLabel}
        >
          <Ionicons name={badge.tone === 'risk' ? 'medkit-outline' : 'newspaper-outline'} size={12} color={badgeColor} />
          <AppText style={[styles.newsBadgeText, { color: badgeColor }]}>{badge.count}</AppText>
        </TouchableOpacity>
      </View>
      {rows.length > 0 ? (
        rows.map(({ key, ...row }, index) => <InsightRow key={key} {...row} last={index === rows.length - 1} />)
      ) : (
        <AppText style={styles.emptyModules}>Nothing urgent in this league right now.</AppText>
      )}
    </View>
  );
}

function SkeletonCard({ styles }: { styles: ReturnType<typeof createStyles> }) {
  return (
    <View style={[styles.card, styles.cardCompact]}>
      <SkeletonBlock width="70%" height={14} />
      <SkeletonBlock width="40%" height={12} style={styles.skeletonGap} />
      <SkeletonBlock width="90%" height={30} style={styles.skeletonGap} />
      <SkeletonBlock width="90%" height={30} style={styles.skeletonGap} />
    </View>
  );
}

function TeaserCard({ styles }: { styles: ReturnType<typeof createStyles> }) {
  return (
    <View style={[styles.card, styles.cardCompact]}>
      {['Record', 'Top add', 'Trade idea', 'Team need'].map((label) => (
        <View key={label} style={styles.teaserRow}>
          <AppText style={styles.teaserLabel}>{label.toUpperCase()}</AppText>
          <View style={styles.teaserBar} />
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { marginBottom: spacing.xl, gap: spacing.sm },
    sectionTitle: {
      fontSize: 13,
      fontWeight: '700',
      color: colors.textSecondary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      paddingHorizontal: spacing.sm,
    },
    grid: { flexDirection: 'row', gap: spacing.sm, alignItems: 'stretch' },
    stack: { gap: spacing.sm },
    // Each league is a genuinely independent unit (Magna Carta §12), so it
    // gets its own surface — the same surface/cardBorder/radius tokens as
    // HomeScreen's league rows, no new card chrome.
    card: {
      backgroundColor: colors.surface,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      borderRadius: radii.md,
      paddingHorizontal: spacing.md,
      paddingTop: spacing.md,
    },
    cardCompact: { flex: 1, minWidth: 0, paddingBottom: spacing.xs },
    cardHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm, paddingBottom: spacing.xs },
    identity: { flex: 1, minWidth: 0 },
    leagueName: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    teamName: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
    recordRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.xs, marginTop: spacing.xs },
    recordValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    recordMeta: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    playoffStatus: { fontSize: 11, fontWeight: '600', color: colors.accentSoft, marginTop: 2 },
    newsBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 3,
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radii.pill,
    },
    newsBadgeText: { fontSize: 12, fontWeight: '700' },
    emptyModules: { fontSize: 12, color: colors.textSecondary, paddingVertical: spacing.md },
    errorText: { fontSize: 12, color: colors.textSecondary, paddingHorizontal: spacing.sm },
    failedNote: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.xs,
      backgroundColor: colors.badgeBackground,
      borderRadius: radii.sm,
      padding: spacing.sm,
    },
    failedNoteText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    skeletonGap: { marginTop: spacing.sm, marginBottom: spacing.xs },
    teaser: { opacity: 0.45 },
    teaserRow: { paddingVertical: spacing.sm, gap: spacing.xs },
    teaserLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4, color: colors.textTertiary },
    teaserBar: { height: 10, width: '80%', borderRadius: radii.sm, backgroundColor: colors.backgroundElevated },
  });
}

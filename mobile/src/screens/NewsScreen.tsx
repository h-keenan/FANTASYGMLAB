import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import PressableScale from '../components/PressableScale';
import AppText from '../components/AppText';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AnimatedCard from '../components/AnimatedCard';
import CompactPlayerModule from '../components/CompactPlayerModule';
import EmptyState from '../components/EmptyState';
import { EventTypePill } from '../components/EventTypeGlyph';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type NewsItem, type NewsResponse } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { newsPlayerIdentities } from '../lib/newsIdentity';
import { alsoReportedLine } from '../lib/playerNews';
import { stubPlayer } from '../lib/playerQuickView';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import NextSteps from '../components/NextSteps';
import { useLastLeague } from '../lib/useLastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import ErrorState from '../components/ErrorState';

// Semantic mapping matches AlertsScreen's (adjacent, roster-tied feed) exactly:
// red = injury/risk, cyan = transaction/GM intelligence, green = role upside,
// gray = everything else. Per Magna Carta §3 an event-type badge must mean the
// same class of thing everywhere in the app, so this stays in lockstep with
// Alerts rather than inventing a News-specific palette.
export function eventBadgeColors(colors: ThemeColors): Record<string, string> {
  return {
    'injury/status': colors.danger,
    transaction: colors.accent,
    'role/depth chart': colors.success,
    'off-field/drama': colors.textSecondary,
  };
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  'injury/status': 'Injury / Status',
  transaction: 'Transaction',
  'role/depth chart': 'Role / Depth Chart',
  'off-field/drama': 'Off-Field',
};

export function eventTypeLabel(eventType: string | null): string {
  if (!eventType) return 'Update';
  return (
    EVENT_TYPE_LABELS[eventType] ??
    eventType
      .split('/')
      .map((part) => part.replace(/\b\w/g, (c) => c.toUpperCase()))
      .join(' / ')
  );
}

function relativeTime(publishedTs: number | null): string {
  if (!publishedTs) return '';
  const seconds = Date.now() / 1000 - publishedTs;
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const DATE_BUCKET_ORDER = ['Today', 'Yesterday', 'Earlier'];

function dateBucket(publishedTs: number | null): string {
  if (!publishedTs) return 'Earlier';
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const published = new Date(publishedTs * 1000);
  if (published >= startOfToday) return 'Today';
  if (published >= startOfYesterday) return 'Yesterday';
  return 'Earlier';
}

interface NewsGroup {
  eventType: string | null;
  items: NewsItem[];
}

/**
 * Clusters consecutive items that share the same event_type into one group,
 * same pattern AlertsScreen uses for its roster-tied feed (Magna Carta §12):
 * a burst of same-type news shares one surface with row dividers instead of
 * repeating an identical bordered card per item. Chronological order within
 * a date bucket is preserved — only adjacent runs merge.
 */
function groupByEventType(items: NewsItem[]): NewsGroup[] {
  const groups: NewsGroup[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.eventType === item.event_type) {
      last.items.push(item);
    } else {
      groups.push({ eventType: item.event_type, items: [item] });
    }
  }
  return groups;
}

function groupByDate(items: NewsItem[]): Array<{ title: string; data: NewsGroup[] }> {
  const buckets = new Map<string, NewsItem[]>();
  for (const item of items) {
    const bucket = dateBucket(item.published_ts);
    const existing = buckets.get(bucket);
    if (existing) existing.push(item);
    else buckets.set(bucket, [item]);
  }
  return DATE_BUCKET_ORDER.filter((bucket) => buckets.has(bucket)).map((bucket) => ({
    title: bucket,
    data: groupByEventType(buckets.get(bucket) ?? []),
  }));
}

export default function NewsScreen({ route }: { route?: { params?: { playerId?: string; playerName?: string } } }) {
  // Filtered to one player when opened from the quick view's "See all news".
  const playerId = route?.params?.playerId;
  const playerName = route?.params?.playerName;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedStatus, setFeedStatus] = useState<NewsResponse['status']>(undefined);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = playerId ? await api.getPlayerNews(playerId, 10, { groupDuplicates: true }) : await api.getNews(30);
      setItems(result.items);
      setFeedStatus('status' in result ? result.status : undefined);
    } catch (err) {
      setError(toUserErrorMessage(err, 'Failed to load news.'));
    } finally {
      setLoading(false);
    }
  }, [playerId]);

  useEffect(() => {
    void load();
  }, [load]);

  const sections = useMemo(() => groupByDate(items), [items]);
  const lastLeague = useLastLeague();

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScreenInfoNote
        text={
          playerId
            ? `Recent injury, role, transaction, and off-field items that mention ${playerName || 'this player'}.`
            : 'General NFL news — injury, role, transaction, and off-field signal only. Not filtered to your specific rosters yet.'
        }
      />

      {error ? <ErrorState compact title="Couldn't load news" message={error} onRetry={() => void load()} /> : null}

      <SectionList
        sections={sections}
        keyExtractor={(group, index) => `${group.eventType ?? 'other'}-${group.items[0]?.link ?? group.items[0]?.title ?? index}`}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        stickySectionHeadersEnabled={false}
        ListFooterComponent={
          !playerId && lastLeague ? (
            <NextSteps
              title="News on your players"
              steps={['alerts']}
              leagueId={lastLeague.leagueId}
              leagueName={lastLeague.leagueName}
            />
          ) : null
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionHeaderText}>{section.title}</AppText>
          </View>
        )}
        ListEmptyComponent={
          !loading ? (
            <EmptyState
              icon="newspaper-outline"
              title={feedStatus?.state === 'warming_up' ? 'News is warming up' : 'No news right now'}
              subtitle={feedStatus?.message || 'Check back later for injury, role, transaction, and off-field updates.'}
            />
          ) : null
        }
        renderItem={({ item: group, index }) => {
          const accentColor = eventBadgeColors(colors)[group.eventType ?? ''] ?? colors.textSecondary;
          // First story of the first cluster in each date bucket is the hero.
          const heroItem = index === 0 ? group.items[0] : null;
          const rest = heroItem ? group.items.slice(1) : group.items;
          return (
            <View style={styles.group}>
              <View style={styles.groupHeaderRow}>
                <EventTypePill
                  eventType={group.eventType}
                  label={eventTypeLabel(group.eventType)}
                  color={accentColor}
                />
              </View>
              {heroItem ? (
                <AccentCard accent={accentColor} compact style={rest.length > 0 ? styles.heroGap : undefined}>
                  <NewsRow item={heroItem} showDivider={false} hero />
                </AccentCard>
              ) : null}
              {rest.length > 0 ? (
                <AnimatedCard style={styles.groupCard}>
                  {rest.map((item, itemIndex) => (
                    <NewsRow
                      key={item.link ?? `${item.title ?? 'item'}-${item.published_ts ?? 0}-${itemIndex}`}
                      item={item}
                      showDivider={itemIndex < rest.length - 1}
                    />
                  ))}
                </AnimatedCard>
              ) : null}
            </View>
          );
        }}
      />
    </View>
  );
}

/** One story row. Exported for the full player profile's News tab. */
export function NewsRow({
  item,
  showDivider,
  showEventTag = false,
  hero = false,
}: {
  item: NewsItem;
  showDivider: boolean;
  /** Prefix the row with its impact tag (Injury / Transaction / ...). */
  showEventTag?: boolean;
  /** First story of a bucket: rendered inside an AccentCard with a larger headline. */
  hero?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createRowStyles(colors), [colors]);
  const footerBits = [
    item.speculative ? 'Unconfirmed / speculative' : null,
    item.source ? `Source: ${item.source}` : null,
  ].filter((bit): bit is string => Boolean(bit));
  // Backend-resolved identities only. Tapping opens the shared quick view
  // with no league (league-independent fields only).
  const { openPlayer } = usePlayerQuickView();
  const identities = newsPlayerIdentities(item);

  return (
    <PressableScale accessibilityRole="button"
      style={[styles.row, hero && styles.rowHero, showDivider && styles.rowDivider]}
      onPress={() => {
        if (item.link) void Linking.openURL(item.link);
      }}
      disabled={!item.link}
    >
      {showEventTag && item.event_type ? (
        <View style={styles.eventTag} testID="news-event-tag">
          <EventTypePill
            eventType={item.event_type}
            label={eventTypeLabel(item.event_type)}
            color={eventBadgeColors(colors)[item.event_type] ?? colors.textSecondary}
          />
        </View>
      ) : null}
      <AppText style={styles.time}>{relativeTime(item.published_ts)}</AppText>
      {identities.map((identity, index) => (
        <CompactPlayerModule
          key={identity.matched_player_id ?? `${identity.matched_player}-${index}`}
          playerId={identity.matched_player_id}
          name={identity.matched_player}
          position={identity.matched_player_position}
          team={identity.matched_player_team}
          style={styles.identity}
          onPress={
            identity.matched_player_id
              ? () =>
                  openPlayer(
                    stubPlayer({
                      player_id: identity.matched_player_id as string,
                      name: identity.matched_player,
                      position: identity.matched_player_position,
                      team: identity.matched_player_team,
                    }),
                    { sourceLabel: 'News' },
                  )
              : undefined
          }
        />
      ))}
      <AppText style={[styles.title, hero && styles.titleHero]} numberOfLines={2}>
        {item.title}
      </AppText>
      {item.summary ? (
        <AppText style={styles.summary} numberOfLines={3}>
          {item.summary}
        </AppText>
      ) : null}
      {alsoReportedLine(item) ? <AppText style={styles.footerMeta}>{alsoReportedLine(item)}</AppText> : null}
      {footerBits.length > 0 ? <AppText style={styles.footerMeta}>{footerBits.join(' · ')}</AppText> : null}
    </PressableScale>
  );
}

function createRowStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { paddingVertical: spacing.sm + 2 },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    eventTag: { marginBottom: spacing.xs, alignSelf: 'flex-start' },
    rowHero: { paddingVertical: 0 },
    time: { fontSize: 12.5, color: colors.textTertiary, marginBottom: 3 },
    identity: { marginBottom: spacing.xs },
    title: { fontSize: 16, fontWeight: '600', color: colors.textPrimary, marginBottom: 3 },
    titleHero: { fontSize: 17, fontWeight: '700' },
    summary: { fontSize: 14.5, color: colors.textSecondary, lineHeight: 20 },
    footerMeta: { fontSize: 12.5, color: colors.textTertiary, marginTop: spacing.xs },
  });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: 'transparent', paddingTop: spacing.md },
    listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3 },
    sectionHeader: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
    sectionHeaderText: {
      fontSize: 13.5,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    group: { marginBottom: spacing.md },
    groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    heroGap: { marginBottom: spacing.sm },
    groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
    error: {
      color: colors.danger,
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.sm,
    },
  });
}

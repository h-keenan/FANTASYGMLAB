import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, RefreshControl, SectionList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type NewsItem } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

// Semantic mapping matches AlertsScreen's (adjacent, roster-tied feed) exactly:
// red = injury/risk, cyan = transaction/GM intelligence, green = role upside,
// gray = everything else. Per Magna Carta §3 an event-type badge must mean the
// same class of thing everywhere in the app, so this stays in lockstep with
// Alerts rather than inventing a News-specific palette.
function eventBadgeColors(colors: ThemeColors): Record<string, string> {
  return {
    'injury/status': colors.danger,
    transaction: colors.accent,
    'role/depth chart': colors.success,
    'off-field/drama': colors.textSecondary,
  };
}

const EVENT_BADGE_ICONS: Record<string, IconName> = {
  'injury/status': 'medkit-outline',
  transaction: 'swap-horizontal-outline',
  'role/depth chart': 'layers-outline',
  'off-field/drama': 'alert-circle-outline',
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  'injury/status': 'Injury / Status',
  transaction: 'Transaction',
  'role/depth chart': 'Role / Depth Chart',
  'off-field/drama': 'Off-Field',
};

function eventTypeLabel(eventType: string | null): string {
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

export default function NewsScreen() {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.getNews(30);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load news.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sections = useMemo(() => groupByDate(items), [items]);

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScreenInfoNote text="General NFL news — injury, role, transaction, and off-field signal only. Not filtered to your specific rosters yet." />

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <SectionList
        sections={sections}
        keyExtractor={(group, index) => `${group.eventType ?? 'other'}-${group.items[0]?.link ?? group.items[0]?.title ?? index}`}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        stickySectionHeadersEnabled={false}
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionHeaderText}>{section.title}</AppText>
          </View>
        )}
        ListEmptyComponent={
          !loading ? (
            <EmptyState
              icon="newspaper-outline"
              title="No news right now"
              subtitle="Check back later for injury, role, transaction, and off-field updates."
            />
          ) : null
        }
        renderItem={({ item: group }) => {
          const accentColor = eventBadgeColors(colors)[group.eventType ?? ''] ?? colors.textSecondary;
          const icon = EVENT_BADGE_ICONS[group.eventType ?? ''] ?? 'information-circle-outline';
          return (
            <View style={styles.group}>
              <View style={styles.groupHeaderRow}>
                <View style={[styles.groupAccentBar, { backgroundColor: accentColor }]} />
                <Ionicons name={icon} size={13} color={accentColor} style={styles.groupIcon} />
                <AppText style={[styles.groupLabel, { color: accentColor }]} numberOfLines={1}>
                  {eventTypeLabel(group.eventType)}
                </AppText>
              </View>
              <AnimatedCard style={styles.groupCard}>
                {group.items.map((item, index) => (
                  <NewsRow
                    key={item.link ?? `${item.title ?? 'item'}-${item.published_ts ?? 0}-${index}`}
                    item={item}
                    showDivider={index < group.items.length - 1}
                  />
                ))}
              </AnimatedCard>
            </View>
          );
        }}
      />
    </View>
  );
}

function NewsRow({ item, showDivider }: { item: NewsItem; showDivider: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createRowStyles(colors), [colors]);
  const footerBits = [
    item.speculative ? 'Unconfirmed / speculative' : null,
    item.source ? `Source: ${item.source}` : null,
  ].filter((bit): bit is string => Boolean(bit));

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.rowDivider]}
      onPress={() => {
        if (item.link) void Linking.openURL(item.link);
      }}
      activeOpacity={item.link ? 0.7 : 1}
      disabled={!item.link}
    >
      <AppText style={styles.time}>{relativeTime(item.published_ts)}</AppText>
      <AppText style={styles.title} numberOfLines={2}>
        {item.title}
      </AppText>
      {item.summary ? (
        <AppText style={styles.summary} numberOfLines={3}>
          {item.summary}
        </AppText>
      ) : null}
      {footerBits.length > 0 ? <AppText style={styles.footerMeta}>{footerBits.join(' · ')}</AppText> : null}
    </TouchableOpacity>
  );
}

function createRowStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { paddingVertical: spacing.sm + 2 },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    time: { fontSize: 11, color: colors.textTertiary, marginBottom: 3 },
    title: { fontSize: 14.5, fontWeight: '600', color: colors.textPrimary, marginBottom: 3 },
    summary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    footerMeta: { fontSize: 11, color: colors.textTertiary, marginTop: spacing.xs },
  });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
    listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3 },
    sectionHeader: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
    sectionHeaderText: {
      fontSize: 12,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    group: { marginBottom: spacing.md },
    groupHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    groupAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
    groupIcon: { marginLeft: -2 },
    groupLabel: {
      flex: 1,
      fontSize: 12,
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
    error: {
      color: colors.danger,
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.sm,
    },
  });
}

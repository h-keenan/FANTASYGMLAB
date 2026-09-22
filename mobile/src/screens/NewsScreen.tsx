import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import { api, type NewsItem } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

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

function groupByDate(items: NewsItem[]): Array<{ title: string; data: NewsItem[] }> {
  const buckets = new Map<string, NewsItem[]>();
  for (const item of items) {
    const bucket = dateBucket(item.published_ts);
    const existing = buckets.get(bucket);
    if (existing) existing.push(item);
    else buckets.set(bucket, [item]);
  }
  return DATE_BUCKET_ORDER.filter((bucket) => buckets.has(bucket)).map((bucket) => ({
    title: bucket,
    data: buckets.get(bucket) ?? [],
  }));
}

export default function NewsScreen() {
  const orbClearance = useOrbClearance();
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
    <View style={styles.container}>
      <GridBackground />
      <AppText style={styles.disclaimer}>
        General NFL news — injury, role, transaction, and off-field signal only. Not filtered to
        your specific rosters yet.
      </AppText>

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <SectionList
        sections={sections}
        keyExtractor={(item, index) => item.link ?? `${item.title ?? 'item'}-${item.published_ts ?? 0}-${index}`}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        stickySectionHeadersEnabled={false}
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <AppText style={styles.sectionHeaderText}>{section.title}</AppText>
          </View>
        )}
        ListEmptyComponent={
          !loading ? <AppText style={styles.empty}>No fantasy-relevant news right now.</AppText> : null
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={StyleSheet.flatten([
              styles.card,
              { borderLeftWidth: 3, borderLeftColor: eventBadgeColors(colors)[item.event_type ?? ''] ?? colors.border },
            ])}
            onPress={() => {
              if (item.link) void Linking.openURL(item.link);
            }}
          >
            <View style={styles.headerRow}>
              {item.event_type ? (
                <View
                  style={[
                    styles.badge,
                    { backgroundColor: eventBadgeColors(colors)[item.event_type] ?? colors.textSecondary },
                  ]}
                >
                  <Ionicons
                    name={EVENT_BADGE_ICONS[item.event_type] ?? 'information-circle-outline'}
                    size={11}
                    color="#fff"
                    style={styles.badgeIcon}
                  />
                  <AppText style={styles.badgeText}>{item.event_type}</AppText>
                </View>
              ) : null}
              <AppText style={styles.time}>{relativeTime(item.published_ts)}</AppText>
            </View>
            <AppText style={styles.title} numberOfLines={2}>
              {item.title}
            </AppText>
            {item.summary ? (
              <AppText style={styles.summary} numberOfLines={3}>
                {item.summary}
              </AppText>
            ) : null}
            {item.speculative ? <AppText style={styles.speculative}>Unconfirmed / speculative</AppText> : null}
            {item.source ? <AppText style={styles.source}>Source: {item.source}</AppText> : null}
          </AnimatedCard>
        )}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
  sectionHeader: { paddingTop: spacing.sm, paddingBottom: spacing.xs },
  sectionHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: { padding: spacing.lg },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  badgeIcon: { marginRight: 4 },
  badgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  time: { fontSize: 12, color: colors.textSecondary },
  title: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginBottom: spacing.xs },
  summary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  speculative: {
    fontSize: 11,
    color: colors.textSecondary,
    fontStyle: 'italic',
    marginTop: spacing.xs,
  },
  source: {
    fontSize: 11,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  });
}

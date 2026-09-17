import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Linking, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import { api, type NewsItem } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { colors, radii, spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const EVENT_BADGE_COLORS: Record<string, string> = {
  'injury/status': colors.danger,
  transaction: colors.accent,
  'role/depth chart': colors.success,
  'off-field/drama': colors.textSecondary,
};

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

export default function NewsScreen() {
  const orbClearance = useOrbClearance();
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

  return (
    <View style={styles.container}>
      <GridBackground />
      <Text style={styles.disclaimer}>
        General NFL news — injury, role, transaction, and off-field signal only. Not filtered to
        your specific rosters yet.
      </Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={items}
        keyExtractor={(item, index) => item.link ?? String(index)}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={
          !loading ? <Text style={styles.empty}>No fantasy-relevant news right now.</Text> : null
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={styles.card}
            onPress={() => {
              if (item.link) void Linking.openURL(item.link);
            }}
          >
            <View style={styles.headerRow}>
              {item.event_type ? (
                <View
                  style={[
                    styles.badge,
                    { backgroundColor: EVENT_BADGE_COLORS[item.event_type] ?? colors.textSecondary },
                  ]}
                >
                  <Ionicons
                    name={EVENT_BADGE_ICONS[item.event_type] ?? 'information-circle-outline'}
                    size={11}
                    color="#fff"
                    style={styles.badgeIcon}
                  />
                  <Text style={styles.badgeText}>{item.event_type}</Text>
                </View>
              ) : null}
              <Text style={styles.time}>{relativeTime(item.published_ts)}</Text>
            </View>
            <Text style={styles.title} numberOfLines={2}>
              {item.title}
            </Text>
            {item.summary ? (
              <Text style={styles.summary} numberOfLines={3}>
                {item.summary}
              </Text>
            ) : null}
            {item.speculative ? <Text style={styles.speculative}>Unconfirmed / speculative</Text> : null}
          </AnimatedCard>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 3, gap: spacing.sm },
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
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
});

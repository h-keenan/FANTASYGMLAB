import React, { useMemo } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import { useThemeMode } from '../context/ThemeModeContext';
import type { NewsItem, PlayerAvailability } from '../lib/api';
import { availabilityDetailParts, newsAgeLabel } from '../lib/playerAvailability';
import { radii, spacing, type ThemeColors } from '../theme';

function metaLine(item: NewsItem): string {
  return [item.source, newsAgeLabel(item.published_ts)].filter(Boolean).join(' · ');
}

function Headline({ item }: { item: NewsItem }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const meta = metaLine(item);
  const body = (
    <>
      <AppText style={[styles.title, item.link ? styles.titleLink : null]}>{item.title || 'Untitled report'}</AppText>
      {meta ? <AppText style={styles.meta}>{meta}</AppText> : null}
    </>
  );
  if (!item.link) return <View style={styles.item}>{body}</View>;
  return (
    <Pressable
      style={styles.item}
      onPress={() => void Linking.openURL(item.link as string)}
      accessibilityRole="link"
      accessibilityLabel={`Open story: ${item.title ?? 'news'}`}
    >
      {body}
    </Pressable>
  );
}

/** Non-healthy status: clean label, body part, honest return note and, when
 * the news pool has one, the latest injury headline (labelled "Latest injury
 * report" — never presented as the proven cause). */
export function AvailabilityBlock({
  availability,
  injuryItem,
  newsLoading,
}: {
  availability: PlayerAvailability;
  injuryItem: NewsItem | null;
  newsLoading: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const detail = availabilityDetailParts(availability).join(' · ');
  return (
    <View
      style={[styles.availability, { borderLeftColor: availability.unavailable ? colors.danger : colors.warning }]}
      testID="pqv-availability"
    >
      <AppText style={styles.availabilityLabel}>{availability.label}</AppText>
      {detail ? <AppText style={styles.meta}>{detail}</AppText> : null}
      {availability.report ? <AppText style={styles.meta}>{availability.report}</AppText> : null}
      {injuryItem ? (
        <View testID="pqv-injury-news">
          <AppText style={styles.kicker}>LATEST INJURY REPORT</AppText>
          <Headline item={injuryItem} />
        </View>
      ) : newsLoading ? (
        <SkeletonBlock height={12} width="80%" />
      ) : null}
    </View>
  );
}

/** Up to 3 recent items. `items === null` = failed/unloaded: renders nothing
 * (or a skeleton while `loading`). A real empty result is one muted line. */
export function LatestNewsSection({
  items,
  loading,
  onSeeAll,
  hideItem,
}: {
  hideItem?: NewsItem | null;
  items: NewsItem[] | null;
  loading: boolean;
  onSeeAll: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (loading) {
    return (
      <View style={styles.section} testID="pqv-news-skeleton">
        <SkeletonBlock height={10} width="30%" />
        <SkeletonBlock height={12} />
        <SkeletonBlock height={12} width="70%" />
      </View>
    );
  }
  if (items === null) return null;
  // The injury headline already shows in the availability block.
  const rest = hideItem ? items.filter((item) => !(item.link === hideItem.link && item.title === hideItem.title)) : items;
  if (rest.length === 0 && hideItem && items.length > 0) return null;
  return (
    <View style={styles.section} testID="pqv-news">
      <SectionHeading title="Latest news" />
      {rest.length === 0 ? (
        <AppText style={styles.meta}>No recent news</AppText>
      ) : (
        <>
          {rest.slice(0, 3).map((item, index) => (
            <View key={`${item.link ?? item.title}-${index}`} style={styles.newsRow}>
              <Headline item={item} />
              {item.summary ? (
                <AppText style={styles.summary} numberOfLines={2}>
                  {item.summary}
                </AppText>
              ) : null}
            </View>
          ))}
          <Pressable onPress={onSeeAll} accessibilityRole="button" hitSlop={8}>
            <AppText style={styles.seeAll}>See all news</AppText>
          </Pressable>
        </>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    availability: {
      gap: 2,
      padding: spacing.sm,
      borderWidth: 1,
      borderLeftWidth: 3,
      borderColor: colors.border,
      borderRadius: radii.sm,
      backgroundColor: colors.glassInset,
    },
    availabilityLabel: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    kicker: { marginTop: spacing.xs, fontSize: 10, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    item: { gap: 1 },
    title: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    titleLink: { textDecorationLine: 'underline' },
    meta: { fontSize: 12, color: colors.textTertiary },
    summary: { fontSize: 12, color: colors.textSecondary },
    section: { gap: spacing.sm },
    newsRow: { gap: 2 },
    seeAll: { fontSize: 13, fontWeight: '700', color: colors.accent },
  });
}

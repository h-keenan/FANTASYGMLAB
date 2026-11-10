import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useInfiniteQuery } from '@tanstack/react-query';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import { AvailabilityBlock } from './PlayerQuickViewNews';
import { SkeletonRow } from './SkeletonBlock';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type NewsItem, type PlayerAvailability } from '../lib/api';
import { flattenNewsPages, groupNewsByDay, PLAYER_NEWS_PAGE_SIZE, sameStory } from '../lib/playerNews';
import { queryKeys } from '../lib/queryKeys';
import { NewsRow } from '../screens/NewsScreen';
import { spacing, type ThemeColors } from '../theme';

/**
 * News tab of the full Player Detail screen (coridian_: "on the full player
 * page, you need a tab for news"). Same GET /v1/players/{id}/news the quick
 * view uses, paged newest-first with syndicated duplicates folded into "Also
 * reported by", every story drawn by the News screen's own NewsRow. A
 * non-healthy player gets the quick view's availability + latest injury
 * report pinned on top. Web twin: web-next PlayerNewsTab.tsx.
 */
export default function PlayerNewsSection({
  playerId,
  availability,
}: {
  playerId: string;
  availability: PlayerAvailability | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const query = useInfiniteQuery({
    queryKey: [...queryKeys.playerQuickView(playerId), 'news-all'],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api.getPlayerNews(playerId, PLAYER_NEWS_PAGE_SIZE, { offset: pageParam, groupDuplicates: true }),
    getNextPageParam: (last) => (last.has_more && last.next_offset != null ? last.next_offset : undefined),
    staleTime: 2 * 60 * 1000,
  });

  if (query.isPending) {
    return (
      <View style={styles.card} testID="player-news-skeleton">
        {Array.from({ length: 4 }, (_, index) => (
          <SkeletonRow key={index} />
        ))}
      </View>
    );
  }

  if (query.isError && !query.data) {
    return (
      <View style={styles.errorBlock} testID="player-news-error">
        <AppText style={styles.muted}>Couldn&apos;t load news right now.</AppText>
        <Button label="Try again" size="sm" onPress={() => void query.refetch()} />
      </View>
    );
  }

  const pages = query.data?.pages ?? [];
  const items = flattenNewsPages(pages);
  const injuryItem = pages[0]?.injury_item ?? null;
  const feedStatus = pages[0]?.status;
  const pinned = availability ? injuryItem : null;
  const listed: NewsItem[] = pinned ? items.filter((item) => !sameStory(item, pinned)) : items;
  const sections = groupNewsByDay(listed);

  return (
    <View style={styles.container} testID="player-news-tab">
      {availability ? <AvailabilityBlock availability={availability} injuryItem={pinned} newsLoading={false} /> : null}

      {feedStatus && feedStatus.state !== 'ok' && feedStatus.message ? (
        <AppText style={styles.muted}>{feedStatus.message}</AppText>
      ) : null}

      {items.length === 0 ? (
        <EmptyState icon="newspaper-outline" title="No recent news" subtitle="Nothing recent mentions this player." />
      ) : (
        sections.map((section) => (
          <View key={section.label} style={styles.section}>
            <AppText style={styles.dayHeading}>{section.label}</AppText>
            <AnimatedCard style={styles.card}>
              {section.items.map((item, index) => (
                <NewsRow
                  key={item.link ?? `${item.title ?? 'item'}-${item.published_ts ?? 0}-${index}`}
                  item={item}
                  showDivider={index < section.items.length - 1}
                  showEventTag
                />
              ))}
            </AnimatedCard>
          </View>
        ))
      )}

      {query.isFetchNextPageError ? <AppText style={styles.muted}>Couldn&apos;t load more news.</AppText> : null}
      {query.hasNextPage ? (
        <Button
          label={query.isFetchingNextPage ? 'Loading…' : query.isFetchNextPageError ? 'Try again' : 'Load more news'}
          variant="secondary"
          size="sm"
          disabled={query.isFetchingNextPage}
          onPress={() => void query.fetchNextPage()}
        />
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { gap: spacing.md },
    section: { gap: spacing.xs },
    dayHeading: {
      fontSize: 13.5,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    card: { padding: spacing.md, paddingVertical: spacing.xs },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    errorBlock: { gap: spacing.sm, alignItems: 'flex-start' },
  });
}

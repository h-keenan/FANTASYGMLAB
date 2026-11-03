"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { NewsCard } from "@/components/NewsContent";
import { AvailabilityBlock } from "@/components/PlayerQuickViewNews";
import { SkeletonRows } from "@/components/Skeleton";
import { api, type NewsFeedStatus, type NewsItem, type PlayerAvailability } from "@/lib/api";
import { appendNewsPage, groupNewsByDay } from "@/lib/newsPresentation";

/**
 * News tab of the full Player Profile (coridian_: "on the full player page,
 * you need a tab for news to see all the news stories"). Reads the same
 * GET /v1/players/{id}/news the Quick View "Latest news" block uses, paged
 * (newest first, PAGE_SIZE at a time) with syndicated duplicates folded into
 * "Also reported by". Reuses the News page's NewsCard for every story. When
 * the player is not healthy, the availability + latest injury report is
 * pinned on top ("why is he out"), exactly the Quick View block.
 */

const PAGE_SIZE = 10;

type LoadState = "loading" | "ready" | "error";

export function PlayerNewsTab({
  playerId,
  availability,
}: {
  playerId: string;
  availability: PlayerAvailability | null;
}) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [injuryItem, setInjuryItem] = useState<NewsItem | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [feedStatus, setFeedStatus] = useState<NewsFeedStatus | null>(null);
  const [moreBusy, setMoreBusy] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const generation = useRef(0);

  const fetchFirst = useCallback(() => {
    const mine = ++generation.current;
    api
      .getPlayerNews(playerId, PAGE_SIZE, { groupDuplicates: true })
      .then((result) => {
        if (mine !== generation.current) return;
        if (!result.ok) {
          setState("error");
          return;
        }
        setItems(result.items);
        setInjuryItem(result.injury_item ?? null);
        setNextOffset(result.has_more ? (result.next_offset ?? null) : null);
        setFeedStatus(result.status ?? null);
        setState("ready");
      })
      .catch(() => {
        if (mine === generation.current) setState("error");
      });
  }, [playerId]);

  useEffect(() => {
    fetchFirst();
    return () => {
      generation.current += 1;
    };
  }, [fetchFirst]);

  const retry = () => {
    setState("loading");
    fetchFirst();
  };

  const loadMore = () => {
    if (nextOffset == null || moreBusy) return;
    const mine = generation.current;
    setMoreBusy(true);
    setMoreError(false);
    api
      .getPlayerNews(playerId, PAGE_SIZE, { offset: nextOffset, groupDuplicates: true })
      .then((result) => {
        if (mine !== generation.current) return;
        if (!result.ok) {
          setMoreError(true);
          return;
        }
        setItems((current) => appendNewsPage(current, result.items));
        setNextOffset(result.has_more ? (result.next_offset ?? null) : null);
      })
      .catch(() => {
        if (mine === generation.current) setMoreError(true);
      })
      .finally(() => {
        if (mine === generation.current) setMoreBusy(false);
      });
  };

  if (state === "loading") {
    return (
      <div aria-hidden="true" data-testid="player-news-skeleton">
        <SkeletonRows count={4} />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="flex flex-col gap-2 items-start" data-testid="player-news-error">
        <p className="pqv-status-text" role="alert">
          Couldn&apos;t load news right now.
        </p>
        <Button size="sm" onClick={retry}>
          Try again
        </Button>
      </div>
    );
  }

  const pinned = availability ? injuryItem : null;
  const listed = pinned
    ? items.filter((item) => !(item.link === pinned.link && item.title === pinned.title))
    : items;
  const sections = groupNewsByDay(listed);
  const feedDegraded = feedStatus != null && feedStatus.state !== "ok";

  return (
    <div className="flex flex-col gap-4" data-testid="player-news-tab">
      {availability ? <AvailabilityBlock availability={availability} injuryItem={pinned} newsLoading={false} /> : null}

      {feedDegraded && feedStatus?.message ? (
        <p className="pqv-status-text" data-testid="player-news-degraded">
          {feedStatus.message}
        </p>
      ) : null}

      {items.length === 0 ? (
        <EmptyState title="No recent news" subtitle="Nothing recent mentions this player." />
      ) : (
        sections.map((section) => (
          <section key={section.label} className="flex flex-col" aria-label={section.label}>
            <h3
              className="uppercase font-extrabold text-xs"
              style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
            >
              {section.label}
            </h3>
            <div className="glass-surface px-3 mt-2">
              {section.items.map((item, index) => (
                <NewsCard key={`${item.link ?? item.title ?? "item"}-${index}`} item={item} showEventTag />
              ))}
            </div>
          </section>
        ))
      )}

      {moreError ? (
        <p className="pqv-status-text" role="alert">
          Couldn&apos;t load more news.
        </p>
      ) : null}
      {nextOffset != null ? (
        <Button size="sm" variant="secondary" onClick={loadMore} disabled={moreBusy}>
          {moreBusy ? "Loading…" : moreError ? "Try again" : "Load more news"}
        </Button>
      ) : null}
    </div>
  );
}

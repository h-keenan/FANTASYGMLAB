"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type AllTradesEntitlement, type AllTradesResponse, type TradeIdea } from "@/lib/api";
import { Button, ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SkeletonCard } from "@/components/Skeleton";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";

/** Ideas per request; the app asks for the same page size (mobile TradeHubScreen). */
const PAGE_SIZE = 3;

/**
 * Trade Hub > All Trades: real trade ideas across every roster in the league, not just yours, three teams at a time with "Load more
 * teams". Same cards as For You (TradeIdeaCardView). Free shows a capped number across the whole tab, then a Pro note.
 * Mobile twin: the All Trades view of mobile/src/screens/TradeHubScreen.tsx.
 */
export function AllTradesSection({ leagueId, strategy, lens }: { leagueId: string; leagueName?: string; strategy?: string; lens: string }) {
  const [ideas, setIdeas] = useState<TradeIdea[]>([]);
  const [cursor, setCursor] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [entitlement, setEntitlement] = useState<AllTradesEntitlement | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shown = useRef(0);

  const request = useCallback(
    (from: number, shownCount: number) =>
      api.getAllTrades(leagueId, {
        strategy: strategy && strategy !== "auto" ? strategy : "retool",
        lens,
        cursor: from,
        pageSize: PAGE_SIZE,
        shownCount,
      }),
    [leagueId, strategy, lens],
  );

  const accept = (result: AllTradesResponse, reset: boolean) => {
    setIdeas((prev) => {
      const next = reset ? result.ideas : [...prev, ...result.ideas];
      shown.current = next.length;
      return next;
    });
    setCursor(result.next_cursor);
    setHasMore(result.has_more);
    setEntitlement(result.entitlement);
  };

  // First view (the parent remounts this when the stance or lens changes, so ideas made under the old one never linger).
  useEffect(() => {
    let cancelled = false;
    request(0, 0)
      .then((result) => {
        if (cancelled) return;
        accept(result, true);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load All Trades.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };

  }, [request, attempt]);

  async function loadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      accept(await request(cursor, shown.current), false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load more teams.");
    } finally {
      setLoadingMore(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" data-testid="all-trades-loading">
        <SkeletonCard lines={4} />
        <SkeletonCard lines={4} />
      </div>
    );
  }
  if (error && ideas.length === 0) {
    return <ErrorState message={error} onRetry={() => { setLoading(true); setError(null); setAttempt((n) => n + 1); }} />;
  }
  if (ideas.length === 0) {
    return (
      <EmptyState title="No trades yet" subtitle="No trade idea cleared the bar for any team yet. Check back after rosters move." />
    );
  }
  const freeGated = Boolean(entitlement && !entitlement.is_premium && entitlement.remaining_free <= 0);
  return (
    <div className="flex flex-col gap-4" data-testid="all-trades">
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Real ideas across every roster in the league, not just yours.</p>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {ideas.map((idea, index) => (
          <TradeIdeaCardView key={`${idea.partner_team_name}-${idea.recommendation_id ?? index}`} idea={idea} leagueId={leagueId} strategy={strategy} lens={lens} />
        ))}
      </div>
      {loadingMore ? <SkeletonCard lines={4} /> : null}
      {error ? <p className="text-xs" role="status" style={{ color: "var(--color-warning)" }}>{error}</p> : null}
      {hasMore && !loadingMore ? (
        freeGated ? (
          <div
            className="p-4 flex flex-col gap-2 premium-glow-card"
            style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)" }}
            data-testid="all-trades-gate"
          >
            <p className="text-sm font-bold">More teams to browse</p>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              Free shows {entitlement?.free_limit} ideas across All Trades. Go Pro to browse every team.
            </p>
            <ButtonLink href="/premium" variant="premium" size="sm">
              Upgrade →
            </ButtonLink>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => void loadMore()}>
            Load more teams
          </Button>
        )
      ) : null}
    </div>
  );
}

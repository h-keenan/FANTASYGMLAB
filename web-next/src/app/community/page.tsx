"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type CommunityTradeItem, type CommunityTradesResponse } from "@/lib/api";
import { CommunityTradesContent } from "@/components/CommunityTradesContent";
import { LoadingScreen } from "@/components/LoadingScreen";

// Like Trade History/Portfolio, Community has no [leagueId] segment — the
// whole point of this feed (docs/roadmap.md's Social/community layer) is
// trades pulled from OTHER users' leagues, never filtered to one.
export default function CommunityPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<CommunityTradesResponse | null>(null);
  const [optedOut, setOptedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([api.getCommunityTrades(), api.getCommunityPreferences()])
      .then(([tradesResult, preferencesResult]) => {
        if (cancelled) return;
        setData(tradesResult);
        setOptedOut(preferencesResult.opted_out);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the Community feed.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  // Optimistic — the reaction endpoint itself returns no fresh counts (see
  // services/mobile_api_service.py's react_to_community_trade), matching
  // the rest of this app's "update local state, fire the request" pattern
  // (e.g. TradeHistoryContent's own answer flow). A failed request is rare
  // enough (own reaction, own token) that this doesn't roll back on error,
  // same tradeoff the existing scouting watchlist follow/unfollow makes.
  const handleReact = useCallback((outcomeId: string, emoji: string, active: boolean) => {
    setData((current) => {
      if (!current) return current;
      const trades: CommunityTradeItem[] = current.trades.map((item) => {
        if (item.id !== outcomeId) return item;
        const nextCount = Math.max(0, (item.reactions[emoji] ?? 0) + (active ? -1 : 1));
        const nextReactions = { ...item.reactions, [emoji]: nextCount };
        if (nextCount === 0) delete nextReactions[emoji];
        const nextMine = active ? item.my_reactions.filter((e) => e !== emoji) : [...item.my_reactions, emoji];
        return { ...item, reactions: nextReactions, my_reactions: nextMine };
      });
      return { ...current, trades };
    });
    api.reactToCommunityTrade(outcomeId, emoji, active ? "remove" : "add").catch(() => {
      // Fail soft — see comment above.
    });
  }, []);

  const handleToggleOptOut = useCallback((nextOptedOut: boolean) => {
    setOptedOut(nextOptedOut);
    return api.updateCommunityPreferences(nextOptedOut).catch(() => {
      // Revert on failure so the toggle never silently lies about state.
      setOptedOut(!nextOptedOut);
    });
  }, []);

  if (authLoading || (!data && !error)) {
    return <LoadingScreen status="Loading the Community feed…" />;
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load the Community feed."}
        </p>
      </main>
    );
  }

  return (
    <CommunityTradesContent
      trades={data.trades}
      reactionEmoji={data.reaction_emoji}
      optedOut={optedOut}
      onReact={handleReact}
      onToggleOptOut={handleToggleOptOut}
    />
  );
}

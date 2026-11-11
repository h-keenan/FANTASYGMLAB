"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type CollegeProspectsResponse, type DraftPickAsset, type PositionNeedGroup } from "@/lib/api";
import { CollegeScoutingContent } from "@/components/CollegeScoutingContent";
import { EmptyState } from "@/components/EmptyState";
import { needPositionsFrom } from "@/lib/scoutingLens";
import { ErrorState } from "@/components/ErrorState";

/**
 * Draft Center's Scouting tab: the shared college prospect board, fetched the
 * first time the tab opens. The prospect pool is league-independent, so no
 * league id is involved.
 */
export function DraftScoutingTab({
  myPicks = [],
  needGroups = null,
}: {
  /** The user's own picks in this league (league overlay). */
  myPicks?: DraftPickAsset[];
  /** My Team position-need groups (league overlay). Null until/unless loaded. */
  needGroups?: PositionNeedGroup[] | null;
}) {
  const [data, setData] = useState<CollegeProspectsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getCollegeProspects()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load College Scouting.");
      });
    return () => {
      cancelled = true;
    };
  }, [retryToken]);

  const lens = useMemo(
    () => (needGroups || myPicks.length > 0 ? { needPositions: needPositionsFrom(needGroups), myPicks } : null),
    [needGroups, myPicks],
  );

  if (error) {
    return (
      <ErrorState
        bare
        message={error}
        onRetry={() => {
          setError(null);
          setRetryToken((n) => n + 1);
        }}
      />
    );
  }
  if (!data) return <EmptyState title="Loading prospects…" />;
  return <CollegeScoutingContent data={data} embedded lens={lens} />;
}

"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type CollegeProspectsResponse, type DraftPickAsset, type PositionNeedGroup } from "@/lib/api";
import { CollegeScoutingContent } from "@/components/CollegeScoutingContent";
import { ErrorState } from "@/components/ErrorState";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SkeletonList } from "@/components/Skeleton";
import { needPositionsFrom } from "@/lib/scoutingLens";

/**
 * Players > Prospects (formerly the College Scouting page and the Draft Center's Scouting tab; 2026-11-16 nav
 * consolidation): the shared college prospect board, fetched the first time the tab opens. The prospect pool is
 * league-independent; the league only adds the "For my league" overlay (your needs and pick slots), loaded best-effort
 * and never blocking the board. Pro, like the page it replaces.
 */
export function ProspectsTab({ leagueId, lens }: { leagueId?: string; lens: string }) {
  const [data, setData] = useState<CollegeProspectsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [myPicks, setMyPicks] = useState<DraftPickAsset[]>([]);
  const [needGroups, setNeedGroups] = useState<PositionNeedGroup[] | null>(null);

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

  // The league overlay inputs (best-effort: no overlay just means the base board).
  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    Promise.all([
      api.getLeagueDraftPicks(leagueId, lens).then((r) => r.picks, () => [] as DraftPickAsset[]),
      api.getMyRoster(leagueId).then((r) => String((r.roster as { roster_id?: unknown } | null)?.roster_id ?? ""), () => ""),
      api.getMyTeamNeeds(leagueId, lens).then((r) => r.position_groups ?? null, () => null),
    ]).then(([picks, rosterId, needs]) => {
      if (cancelled) return;
      setMyPicks(rosterId ? picks.filter((pick) => pick.owner_roster_id === rosterId) : []);
      setNeedGroups(needs);
    });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens]);

  const scoutingLens = useMemo(
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
  if (!data) return <SkeletonList label="prospects" count={6} />;
  if (data.is_premium === false) {
    return (
      <PremiumUpsellCard
        bare
        kicker="College Scouting"
        upsell={data.upsell ?? null}
        fallbackTitle="Scout the next rookie class"
        fallbackBody="College Scouting is a Pro feature: the shared prospect board, community grades, your own scouting reports and watchlist. Start your free trial to unlock it."
      />
    );
  }
  return <CollegeScoutingContent data={data} embedded lens={scoutingLens} />;
}

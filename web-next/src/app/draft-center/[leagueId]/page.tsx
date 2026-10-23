"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type DraftCenterResponse, type DraftPickAsset } from "@/lib/api";
import { DraftCenterContent } from "@/components/DraftCenterContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function DraftCenterPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("draft_center_opened", { leagueId });
  }, [session, leagueId]);

  const [draftCenter, setDraftCenter] = useState<DraftCenterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Picks and the caller's own roster are additive to the page — neither
  // should be able to blank out the posture/insight cards that already
  // loaded, so both degrade quietly instead of blocking the page, same
  // contract mobile's DraftCenterScreen.tsx follows.
  const [picks, setPicks] = useState<DraftPickAsset[]>([]);
  const [myRosterId, setMyRosterId] = useState<string>("");

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueDraftCenter(leagueId, lens)
      .then((result) => {
        if (!cancelled) setDraftCenter(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Draft Center.");
      });

    api
      .getLeagueDraftPicks(leagueId, lens)
      .then((result) => {
        if (!cancelled) setPicks(result.picks);
      })
      .catch(() => {
        /* best-effort */
      });

    api
      .getMyRoster(leagueId)
      .then((result) => {
        if (!cancelled && result.roster) {
          setMyRosterId(String((result.roster as { roster_id?: unknown }).roster_id ?? ""));
        }
      })
      .catch(() => {
        /* best-effort */
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!draftCenter && !error)) {
    return (
      <LoadingScreen status="Loading Draft Center…" />
    );
  }

  if (error || !draftCenter) {
    return (
      <ErrorState message={error || "Could not load Draft Center."} onRetry={reloadPage} />
    );
  }

  return (
    <DraftCenterContent leagueName={leagueName} data={draftCenter} picks={picks} myRosterId={myRosterId} />
  );
}

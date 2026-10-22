"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { trackFeatureUse } from "@/lib/analytics";
import {
  api,
  ApiError,
  type LiveDraftDiscoveryResponse,
  type LiveDraftStateResponse,
} from "@/lib/api";
import {
  diffRankMovement,
  diffTeamRankMovement,
  ranksById,
  teamRanksById,
} from "@/lib/liveDraftPresentation";
import { LiveDraftContent } from "@/components/LiveDraftContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Matches modules/live_draft.py's LIVE_DRAFT_POLL_INTERVAL_SECONDS (12s) —
// the same cadence modules/live_draft_ui.py's Streamlit route already
// polls Sleeper at via st.fragment(run_every=...). Polling stops once the
// selected draft's status is "complete" (same gate that Streamlit route
// applies before deciding whether to even register its polling fragment).
const POLL_INTERVAL_MS = 12_000;

export default function LiveDraftPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [discovery, setDiscovery] = useState<LiveDraftDiscoveryResponse | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<string>("");
  const [draftState, setDraftState] = useState<LiveDraftStateResponse | null>(null);
  const [stateError, setStateError] = useState<string | null>(null);

  // Rank-movement tracking lives here, not in LiveDraftContent — it needs
  // to persist across polls without triggering its own re-render cycle
  // (see lib/liveDraftPresentation.ts's module comment for why the server
  // never tracks this itself).
  const previousRanksRef = useRef<Record<string, number>>({});
  const previousTeamRanksRef = useRef<Record<string, number>>({});

  useEffect(() => {
    if (!session) return;
    trackFeatureUse("live_draft_opened", { leagueId });
  }, [session, leagueId]);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;
    api
      .getLiveDraftDiscovery(leagueId)
      .then((result) => {
        if (cancelled) return;
        setDiscovery(result);
        const liveOrPaused = result.drafts.filter(
          (draft) => draft.status === "drafting" || draft.status === "paused",
        );
        const preferred = result.active_draft_id || liveOrPaused[0]?.draft_id || "";
        setSelectedDraftId(preferred);
      })
      .catch((err) => {
        if (!cancelled) setDiscoveryError(err instanceof Error ? err.message : "Could not reach Sleeper.");
      });
    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  const fetchSnapshot = useCallback(async () => {
    if (!selectedDraftId) return;
    try {
      const result = await api.getLiveDraftState(leagueId, selectedDraftId, lens);
      // coridian_, 2026-10-18: "Live draft needs to be locked." A Free
      // caller's discovery.is_premium already keeps LiveDraftContent from
      // ever rendering the board, but this poll still runs underneath it
      // (selectedDraftId gets set from the still-ungated drafts list) —
      // the locked response has no rankings/team_rankings at all, so skip
      // the diff/map entirely instead of crashing on undefined.
      if (!result.is_premium) {
        setDraftState(result);
        setStateError(null);
        return;
      }
      const movement = diffRankMovement(result.rankings, previousRanksRef.current);
      const teamMovement = diffTeamRankMovement(result.team_rankings, previousTeamRanksRef.current);
      previousRanksRef.current = ranksById(result.rankings);
      previousTeamRanksRef.current = teamRanksById(result.team_rankings);
      setDraftState({
        ...result,
        rankings: result.rankings.map((row) => ({ ...row, movement: movement[row.player_id] ?? 0 })),
        team_rankings: result.team_rankings.map((row) => ({
          ...row,
          movement: teamMovement[String(row.roster_id)] ?? 0,
        })),
      });
      setStateError(null);
    } catch (err) {
      // Best-effort, same "keep showing the last valid board" degradation
      // modules/live_draft_ui.py's Streamlit route applies on a transient
      // Sleeper hiccup — a failed poll never blanks an already-loaded page.
      if (!draftState) {
        setStateError(
          err instanceof ApiError ? err.message : "Could not load the live draft board.",
        );
      }
    }
  }, [leagueId, selectedDraftId, lens, draftState]);

  useEffect(() => {
    if (!selectedDraftId) return;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | null = null;

    const run = async () => {
      if (cancelled) return;
      await fetchSnapshot();
    };

    run();
    interval = setInterval(() => {
      // Stop polling once the draft is complete — re-checked every tick
      // instead of only at mount, since a draft can finish mid-session.
      setDraftState((current) => {
        if (current?.status === "complete" && interval) {
          clearInterval(interval);
          interval = null;
        }
        return current;
      });
      run();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDraftId, lens]);

  if (authLoading || (!discovery && !discoveryError)) {
    return (
      <LoadingScreen status="Loading Live Draft…" />
    );
  }

  if (discoveryError || !discovery) {
    return (
      <ErrorState message={discoveryError || "Could not reach Sleeper."} onRetry={reloadPage} />
    );
  }

  return (
    <LiveDraftContent
      leagueId={leagueId}
      leagueName={leagueName}
      discovery={discovery}
      selectedDraftId={selectedDraftId}
      onSelectDraft={(draftId) => {
        previousRanksRef.current = {};
        previousTeamRanksRef.current = {};
        setDraftState(null);
        setSelectedDraftId(draftId);
      }}
      state={draftState}
      stateError={stateError}
      onRefresh={() => {
        fetchSnapshot();
      }}
      lens={lens}
    />
  );
}

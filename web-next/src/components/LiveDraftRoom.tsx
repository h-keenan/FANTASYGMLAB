"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
  liveDraftIds,
  ranksById,
  teamRanksById,
} from "@/lib/liveDraftPresentation";
import { LiveDraftContent } from "@/components/LiveDraftContent";

// Matches modules/live_draft.py's LIVE_DRAFT_POLL_INTERVAL_SECONDS (12s) —
// the same cadence modules/live_draft_ui.py's Streamlit route already
// polls Sleeper at via st.fragment(run_every=...). Polling stops once the
// selected draft's status is "complete" (same gate that Streamlit route
// applies before deciding whether to even register its polling fragment).
const POLL_INTERVAL_MS = 12_000;

/**
 * The live draft room, hosted as the "Live room" tab of the Draft page (the standalone Live Draft page is retired and
 * redirects to /draft-center/[id]?tab=live). The Draft page reads the discovery once (to decide whether the tab exists at
 * all) and hands it in; this component owns the 12s snapshot polling.
 */
export function LiveDraftRoom({
  leagueId,
  leagueName,
  discovery,
  lens,
}: {
  leagueId: string;
  leagueName: string;
  discovery: LiveDraftDiscoveryResponse;
  lens: string;
}) {
  const [selectedDraftId, setSelectedDraftId] = useState<string>(() => liveDraftIds(discovery).preferred);
  const [draftState, setDraftState] = useState<LiveDraftStateResponse | null>(null);
  const [stateError, setStateError] = useState<string | null>(null);

  // Rank-movement tracking lives here, not in LiveDraftContent — it needs
  // to persist across polls without triggering its own re-render cycle
  // (see lib/liveDraftPresentation.ts's module comment for why the server
  // never tracks this itself).
  const previousRanksRef = useRef<Record<string, number>>({});
  const previousTeamRanksRef = useRef<Record<string, number>>({});

  useEffect(() => {
    trackFeatureUse("live_draft_opened", { leagueId });
  }, [leagueId]);

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
      embedded
    />
  );
}

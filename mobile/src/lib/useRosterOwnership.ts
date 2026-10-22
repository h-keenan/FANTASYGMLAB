import { useEffect, useState } from 'react';

import { api } from './api';
import { rosterOwnershipFrom, type RosterOwnership } from './tradeShortcuts';

/**
 * Who owns which player in this league — the user's own roster plus every
 * rostered id — for the "Add to Trade" / "Find trades" shortcuts. Same two
 * endpoints Trade Analyzer already reads (/my-roster, /rosters). Null until
 * loaded, and stays null on failure or when the user has no roster here, so
 * callers just hide the shortcuts rather than guessing.
 */
export function useRosterOwnership(leagueId: string): RosterOwnership | null {
  const [ownership, setOwnership] = useState<RosterOwnership | null>(null);

  useEffect(() => {
    let cancelled = false;
    setOwnership(null);
    Promise.all([api.getMyRoster(leagueId), api.getLeagueRosters(leagueId)])
      .then(([myRoster, rosters]) => {
        if (cancelled || myRoster.reason || !myRoster.roster) return;
        setOwnership(rosterOwnershipFrom(myRoster.roster, rosters.rosters ?? []));
      })
      .catch(() => {
        // Best-effort: no ownership means no trade shortcuts, never a guess.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  return ownership;
}

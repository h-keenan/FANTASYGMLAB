import { useEffect, useState } from 'react';

import { api } from './api';
import { rosterOwnershipFrom, type RosterOwnership } from './tradeShortcuts';

export interface RosterOwnershipWithTeams {
  ownership: RosterOwnership | null;
  /** Team display name per roster_id; empty until (or unless) team profiles load. */
  teamNameByRosterId: Record<string, string>;
}

/**
 * Who owns which player in this league — the user's own roster plus every
 * rostered id — for the "Add to Trade" / "Find trades" shortcuts and the
 * player's league status ("Free agent" / "On <team>"). Same endpoints Trade
 * Analyzer already reads (/my-roster, /rosters, /team-profiles). Ownership
 * stays null on failure or when the user has no roster here, so callers just
 * hide the shortcuts / status rather than guessing. Team names are
 * best-effort: a status without a name is still correct.
 */
export function useRosterOwnershipWithTeams(leagueId: string): RosterOwnershipWithTeams {
  const [state, setState] = useState<RosterOwnershipWithTeams>({ ownership: null, teamNameByRosterId: {} });

  useEffect(() => {
    let cancelled = false;
    setState({ ownership: null, teamNameByRosterId: {} });
    Promise.all([
      api.getMyRoster(leagueId),
      api.getLeagueRosters(leagueId),
      api.getLeagueTeamProfiles(leagueId).catch(() => null),
    ])
      .then(([myRoster, rosters, profiles]) => {
        if (cancelled || myRoster.reason || !myRoster.roster) return;
        const teamNameByRosterId: Record<string, string> = {};
        for (const profile of Object.values(profiles?.profiles ?? {})) {
          if (profile?.team_name) teamNameByRosterId[String(profile.roster_id)] = profile.team_name;
        }
        setState({ ownership: rosterOwnershipFrom(myRoster.roster, rosters.rosters ?? []), teamNameByRosterId });
      })
      .catch(() => {
        // Best-effort: no ownership means no trade shortcuts, never a guess.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  return state;
}

export function useRosterOwnership(leagueId: string): RosterOwnership | null {
  return useRosterOwnershipWithTeams(leagueId).ownership;
}

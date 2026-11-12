import { useEffect, useState } from 'react';

import { api } from './api';
import { simGameReasonMessage, simPreselectedRosterId, type SimImportTeam } from './simGame';

export type SimLeagueTeamsState =
  | { status: 'idle' | 'loading' }
  | { status: 'ready'; teams: SimImportTeam[]; youRosterId: string }
  | { status: 'error'; message: string };

/**
 * The picked league's teams for the 'which team is yours' picker. Read-only;
 * `youRosterId` is the account's own roster ('' when it could not be told, so
 * the player picks). Errors carry plain words (ESPN leagues, sizes the game
 * cannot play, Sleeper down).
 */
export function useSimLeagueTeams(leagueId: string, onResolved: (youRosterId: string) => void): SimLeagueTeamsState {
  const [state, setState] = useState<{ key: string; value: SimLeagueTeamsState }>({ key: '', value: { status: 'idle' } });
  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    api.getSimLeagueTeams(leagueId).then(
      (res) => {
        if (cancelled) return;
        if (res.reason || !res.teams?.length) {
          setState({ key: leagueId, value: { status: 'error', message: simGameReasonMessage(res.reason || 'league_unavailable', res) } });
          onResolved('');
          return;
        }
        const youRosterId = simPreselectedRosterId(res);
        setState({ key: leagueId, value: { status: 'ready', teams: res.teams, youRosterId } });
        onResolved(youRosterId);
      },
      () => {
        if (cancelled) return;
        setState({ key: leagueId, value: { status: 'error', message: "We could not load that league's teams. Try again." } });
        onResolved('');
      },
    );
    return () => {
      cancelled = true;
    };
    // onResolved is a state setter wrapper; the fetch must run once per league.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId]);
  if (!leagueId) return { status: 'idle' };
  return state.key === leagueId ? state.value : { status: 'loading' };
}

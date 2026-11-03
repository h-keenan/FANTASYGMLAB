import { useEffect, useState } from 'react';

import { getLastLeague, type LastLeague } from './lastLeague';

/**
 * The league the person last opened, for league-less screens (News, Trade
 * History, Community) that want a "next step" into a league page. `null`
 * until read and when there is none, so the link is simply not shown.
 */
export function useLastLeague(): LastLeague | null {
  const [league, setLeague] = useState<LastLeague | null>(null);
  useEffect(() => {
    let cancelled = false;
    void getLastLeague().then((last) => {
      if (!cancelled) setLeague(last);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return league;
}

import type {
  PortfolioFailedLeague,
  PortfolioIndexResponse,
  PortfolioLeague,
  PortfolioLeagueResponse,
  PortfolioSavedLeague,
} from './api';

/**
 * Progressive Portfolio (mirrors web-next/src/lib/portfolioProgress.ts).
 *
 * GET /v1/portfolio answers only after EVERY saved league's summary is
 * built, and that per-league work is CPU-bound and shares one server
 * process. PortfolioScreen instead loads the cheap index (GET
 * /v1/portfolio/leagues) and then each league's own row as its own query,
 * so rows paint as they arrive and the per-league requests spread across
 * the API's worker processes. This folds the index plus whatever per-league
 * results have landed so far into ordered rows — a loaded league or a
 * still-loading placeholder — plus the leagues that couldn't load.
 */

export type PortfolioLeagueState =
  | { status: 'pending' }
  | { status: 'success'; data: PortfolioLeagueResponse }
  | { status: 'error' };

export type PortfolioRow =
  | { kind: 'league'; league: PortfolioLeague }
  | { kind: 'pending'; league: PortfolioSavedLeague };

export interface ComposedPortfolio {
  /** Loaded leagues and still-loading placeholders, in saved-league order. */
  rows: PortfolioRow[];
  leagues: PortfolioLeague[];
  failedLeagues: PortfolioFailedLeague[];
  pendingCount: number;
  settled: boolean;
}

export function composePortfolio(
  index: PortfolioIndexResponse,
  states: Record<string, PortfolioLeagueState | undefined>,
): ComposedPortfolio {
  const rows: PortfolioRow[] = [];
  const leagues: PortfolioLeague[] = [];
  const failedLeagues: PortfolioFailedLeague[] = [];
  let pendingCount = 0;
  if (!index.is_premium) {
    return { rows, leagues, failedLeagues, pendingCount, settled: true };
  }
  for (const saved of index.saved_leagues ?? []) {
    const state = states[saved.league_id];
    if (!state || state.status === 'pending') {
      rows.push({ kind: 'pending', league: saved });
      pendingCount += 1;
      continue;
    }
    if (state.status === 'success' && state.data.league) {
      rows.push({ kind: 'league', league: state.data.league });
      leagues.push(state.data.league);
      continue;
    }
    if (state.status === 'success' && state.data.failed_league) {
      failedLeagues.push(state.data.failed_league);
      continue;
    }
    // A request error, or a response with neither row (e.g. entitlement
    // changed mid-load) — reported like any other league that couldn't
    // load, never silently dropped.
    failedLeagues.push({ league_id: saved.league_id, league_name: saved.league_name, reason: 'unavailable' });
  }
  return { rows, leagues, failedLeagues, pendingCount, settled: pendingCount === 0 };
}

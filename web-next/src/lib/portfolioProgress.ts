import type {
  PortfolioFailedLeague,
  PortfolioIndexResponse,
  PortfolioLeague,
  PortfolioLeagueResponse,
  PortfolioResponse,
  PortfolioSavedLeague,
} from "@/lib/api";

/**
 * Progressive Portfolio (mirrors mobile/src/lib/portfolioProgress.ts).
 *
 * GET /v1/portfolio returns only after EVERY saved league's summary is
 * built, and that per-league work is CPU-bound and shares one server
 * process. The page instead loads the cheap index (GET
 * /v1/portfolio/leagues) and then each league's own row concurrently, so
 * cards paint as they arrive and the per-league requests spread across
 * the API's worker processes. This folds the index plus whatever per-league
 * results have landed so far into the same PortfolioResponse shape
 * PortfolioContent already renders, plus the still-loading leagues (in
 * saved order) so the page can hold their place with skeleton cards.
 */

export type PortfolioLeagueState =
  | { status: "pending" }
  | { status: "success"; data: PortfolioLeagueResponse }
  | { status: "error" };

export interface ComposedPortfolio {
  response: PortfolioResponse;
  /** Saved-league order, for placing loaded cards and skeletons. */
  order: string[];
  pending: PortfolioSavedLeague[];
  /** Leagues whose card has its headline but whose signals are still being computed. */
  signalsPending: string[];
  settled: boolean;
}

export function composePortfolio(
  index: PortfolioIndexResponse,
  states: Record<string, PortfolioLeagueState | undefined>,
): ComposedPortfolio {
  const base: PortfolioResponse = {
    ok: index.ok,
    is_premium: index.is_premium,
    lens: index.lens,
    leagues: [],
    failed_leagues: [],
    upsell: index.upsell,
    ...(index.reason ? { reason: index.reason } : {}),
  };
  if (!index.is_premium) {
    return { response: base, order: [], pending: [], signalsPending: [], settled: true };
  }

  const leagues: PortfolioLeague[] = [];
  const failed: PortfolioFailedLeague[] = [];
  const pending: PortfolioSavedLeague[] = [];
  const order: string[] = [];
  const signalsPending: string[] = [];
  for (const saved of index.saved_leagues ?? []) {
    order.push(saved.league_id);
    const state = states[saved.league_id];
    if (!state || state.status === "pending") {
      pending.push(saved);
      continue;
    }
    if (state.status === "success" && state.data.league) {
      leagues.push(state.data.league);
      if (state.data.signals_pending) signalsPending.push(saved.league_id);
      continue;
    }
    if (state.status === "success" && state.data.failed_league) {
      failed.push(state.data.failed_league);
      continue;
    }
    // A request error, or a response with neither row (e.g. entitlement
    // changed mid-load) — reported like any other league that couldn't
    // load, never silently dropped.
    failed.push({ league_id: saved.league_id, league_name: saved.league_name, reason: "unavailable" });
  }
  return {
    response: { ...base, leagues, failed_leagues: failed },
    order,
    pending,
    signalsPending,
    // Settled = every league has a row AND no card is still waiting on signals.
    settled: pending.length === 0 && signalsPending.length === 0,
  };
}

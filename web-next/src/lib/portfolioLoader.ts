import type { PortfolioLeagueResponse } from "@/lib/api";
import type { PortfolioLeagueState } from "@/lib/portfolioProgress";

/**
 * Bounded, abortable, windowed, two-phase per-league loader for the
 * progressive Portfolio (mirrors mobile/src/lib/portfolioLoader.ts; the code
 * between the SHARED markers must stay identical, scripts/check_lib_twins.mjs
 * enforces it).
 *
 * Each league's row is expensive server-side, so instead of firing one
 * request per saved league at once:
 *  - at most PORTFOLIO_LEAGUE_CONCURRENCY requests run at a time, in saved
 *    order (the leagues at the top of the page fill first);
 *  - only the first PORTFOLIO_EAGER_LEAGUES leagues load up front; the rest
 *    wait for `unlock()` (the page calls it as the list scrolls near them), so
 *    a 12-league account that never scrolls never pays for the bottom half;
 *  - each league is two requests: a "headline" request (record, ranks,
 *    archetype, top asset, health: the server skips the trade-idea search) and,
 *    only when the server says `signals_pending`, a "full" request that fills
 *    in the signals. Every league's headline is queued ahead of any league's
 *    full request, so all the cards have their identity before the slow part;
 *  - leagues the caller already has complete data for (`warm`: stale-while-
 *    revalidate) skip the headline and go straight to a full revalidation.
 * One league failing never blocks the queue; `retry` re-queues just that row.
 * `abort` (page unmount / refresh) cancels in-flight requests and drops
 * everything still queued.
 */

// SHARED BEGIN
/** Max per-league requests in flight at once. */
export const PORTFOLIO_LEAGUE_CONCURRENCY = 3;
/** Show the branded splash only if the first paint is still empty after this. */
export const PORTFOLIO_SPLASH_DELAY_MS = 300;
/** Skeleton rows shown before the index says how many leagues there are. */
export const PORTFOLIO_SHELL_SKELETON_COUNT = 3;
/** Leagues loaded before the user scrolls (about one screen plus a buffer). */
export const PORTFOLIO_EAGER_LEAGUES = 6;
/** Leagues released each time the list scrolls near the unloaded ones. */
export const PORTFOLIO_UNLOCK_STEP = 3;
/** A saved Portfolio younger than this is shown as is, without revalidating. */
export const PORTFOLIO_FRESH_MS = 30_000;

export type PortfolioLoadPhase = "headline" | "full";

export interface LeagueLoader {
  /** Re-queue one league (e.g. its inline "Retry"); a no-op while it is loading. */
  retry: (leagueId: string) => void;
  /** Release the next `count` leagues (default PORTFOLIO_UNLOCK_STEP) for loading. */
  unlock: (count?: number) => void;
  /** Release every remaining league (e.g. before sharing the whole portfolio). */
  unlockAll: () => void;
  abort: () => void;
}

export function startLeagueLoader({
  leagueIds,
  load,
  onState,
  warm = [],
  skip = [],
  concurrency = PORTFOLIO_LEAGUE_CONCURRENCY,
  eager = PORTFOLIO_EAGER_LEAGUES,
}: {
  leagueIds: string[];
  load: (leagueId: string, signal: AbortSignal, phase: PortfolioLoadPhase) => Promise<PortfolioLeagueResponse>;
  onState: (leagueId: string, state: PortfolioLeagueState) => void;
  /** Leagues already showing complete (stale) data: revalidated with one full request. */
  warm?: string[];
  /** Leagues whose data is fresh enough to leave alone. */
  skip?: string[];
  concurrency?: number;
  eager?: number;
}): LeagueLoader {
  const controller = new AbortController();
  const cap = Math.max(1, concurrency);
  const position = new Map(leagueIds.map((leagueId, index) => [leagueId, index]));
  const skipped = new Set(skip);
  const warmIds = new Set(warm);
  const headlineQueue: string[] = leagueIds.filter((leagueId) => !skipped.has(leagueId) && !warmIds.has(leagueId));
  const fullQueue: string[] = leagueIds.filter((leagueId) => !skipped.has(leagueId) && warmIds.has(leagueId));
  const active = new Set<string>();
  let limit = Math.max(0, eager);

  const unlocked = (leagueId: string) => (position.get(leagueId) ?? 0) < limit;
  const takeNext = (): { leagueId: string; phase: PortfolioLoadPhase } | null => {
    const headlineAt = headlineQueue.findIndex(unlocked);
    if (headlineAt >= 0) return { leagueId: headlineQueue.splice(headlineAt, 1)[0], phase: "headline" };
    const fullAt = fullQueue.findIndex(unlocked);
    if (fullAt >= 0) return { leagueId: fullQueue.splice(fullAt, 1)[0], phase: "full" };
    return null;
  };

  const pump = () => {
    while (!controller.signal.aborted && active.size < cap) {
      const next = takeNext();
      if (!next) return;
      const { leagueId, phase } = next;
      active.add(leagueId);
      load(leagueId, controller.signal, phase)
        .then(
          (data): PortfolioLeagueState => ({ status: "success", data }),
          (): PortfolioLeagueState => ({ status: "error" }),
        )
        .then((state) => {
          active.delete(leagueId);
          if (controller.signal.aborted) return;
          if (phase === "full" && warmIds.has(leagueId) && state.status === "error") {
            // A failed background revalidation never blanks the stale data on screen.
            pump();
            return;
          }
          onState(leagueId, state);
          if (phase === "headline" && state.status === "success" && state.data.signals_pending) {
            fullQueue.push(leagueId);
          }
          pump();
        });
    }
  };

  pump();

  return {
    retry: (leagueId) => {
      if (controller.signal.aborted || active.has(leagueId)) return;
      if (headlineQueue.includes(leagueId) || fullQueue.includes(leagueId)) {
        // Already queued: if it is only waiting on the window, "try again" lets it through.
        limit = Math.max(limit, (position.get(leagueId) ?? 0) + 1);
        pump();
        return;
      }
      onState(leagueId, { status: "pending" });
      limit = Math.max(limit, (position.get(leagueId) ?? 0) + 1);
      headlineQueue.push(leagueId);
      pump();
    },
    unlock: (count = PORTFOLIO_UNLOCK_STEP) => {
      limit = Math.min(leagueIds.length, limit + Math.max(1, count));
      pump();
    },
    unlockAll: () => {
      limit = leagueIds.length;
      pump();
    },
    abort: () => {
      controller.abort();
      headlineQueue.length = 0;
      fullQueue.length = 0;
    },
  };
}
// SHARED END

/** Shared by the real card and its skeleton so a row never changes height when it fills in. */
export const PORTFOLIO_CARD_MIN_HEIGHT = 176;

import type { PortfolioLeagueResponse } from "@/lib/api";
import type { PortfolioLeagueState } from "@/lib/portfolioProgress";

/**
 * Bounded, abortable per-league loader for the progressive Portfolio
 * (mirrors mobile/src/lib/portfolioLoader.ts).
 *
 * Each league's row is expensive server-side, so instead of firing one
 * request per saved league at once, at most PORTFOLIO_LEAGUE_CONCURRENCY run
 * at a time, in saved order (the leagues at the top of the page fill first).
 * One league failing never blocks the queue; `retry` re-queues just that row.
 * `abort` (page unmount / refresh) cancels in-flight requests and drops
 * everything still queued.
 */

/** Max per-league requests in flight at once. */
export const PORTFOLIO_LEAGUE_CONCURRENCY = 3;
/** Show the branded splash only if the first paint is still empty after this. */
export const PORTFOLIO_SPLASH_DELAY_MS = 300;
/** Shared by the real card and its skeleton so a row never changes height when it fills in. */
export const PORTFOLIO_CARD_MIN_HEIGHT = 176;
/** Skeleton rows shown before the index says how many leagues there are. */
export const PORTFOLIO_SHELL_SKELETON_COUNT = 3;

export interface LeagueLoader {
  /** Re-queue one league (e.g. its inline "Retry"); a no-op while it is loading. */
  retry: (leagueId: string) => void;
  abort: () => void;
}

export function startLeagueLoader({
  leagueIds,
  load,
  onState,
  concurrency = PORTFOLIO_LEAGUE_CONCURRENCY,
}: {
  leagueIds: string[];
  load: (leagueId: string, signal: AbortSignal) => Promise<PortfolioLeagueResponse>;
  onState: (leagueId: string, state: PortfolioLeagueState) => void;
  concurrency?: number;
}): LeagueLoader {
  const controller = new AbortController();
  const queue: string[] = [...leagueIds];
  const active = new Set<string>();
  const cap = Math.max(1, concurrency);

  const pump = () => {
    while (!controller.signal.aborted && active.size < cap && queue.length > 0) {
      const leagueId = queue.shift() as string;
      active.add(leagueId);
      load(leagueId, controller.signal)
        .then(
          (data): PortfolioLeagueState => ({ status: "success", data }),
          (): PortfolioLeagueState => ({ status: "error" }),
        )
        .then((state) => {
          active.delete(leagueId);
          if (controller.signal.aborted) return;
          onState(leagueId, state);
          pump();
        });
    }
  };

  pump();

  return {
    retry: (leagueId) => {
      if (controller.signal.aborted || active.has(leagueId) || queue.includes(leagueId)) return;
      onState(leagueId, { status: "pending" });
      queue.push(leagueId);
      pump();
    },
    abort: () => {
      controller.abort();
      queue.length = 0;
    },
  };
}

import { describe, expect, it, vi } from "vitest";

import type { PortfolioLeagueResponse } from "@/lib/api";
import { PORTFOLIO_LEAGUE_CONCURRENCY, startLeagueLoader } from "@/lib/portfolioLoader";
import type { PortfolioLeagueState } from "@/lib/portfolioProgress";

function response(id: string): PortfolioLeagueResponse {
  return { ok: true, is_premium: true, lens: "Dynasty", league: null, failed_league: null, upsell: null, _id: id } as never;
}

/** A load() whose promises the test resolves/rejects by hand. */
function controllable() {
  const calls: string[] = [];
  const pending = new Map<string, { resolve: (v: PortfolioLeagueResponse) => void; reject: (e: unknown) => void }>();
  let inFlight = 0;
  let maxInFlight = 0;
  const signals = new Map<string, AbortSignal>();
  const load = (id: string, signal: AbortSignal) => {
    calls.push(id);
    signals.set(id, signal);
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    return new Promise<PortfolioLeagueResponse>((resolve, reject) => {
      pending.set(id, {
        resolve: (v) => {
          inFlight -= 1;
          resolve(v);
        },
        reject: (e) => {
          inFlight -= 1;
          reject(e);
        },
      });
    });
  };
  return { load, calls, pending, signals, maxInFlight: () => maxInFlight };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("startLeagueLoader", () => {
  it("starts leagues in saved order and never exceeds the concurrency cap", async () => {
    const c = controllable();
    const ids = ["a", "b", "c", "d", "e", "f", "g"];
    const states: Record<string, PortfolioLeagueState> = {};
    startLeagueLoader({ leagueIds: ids, load: c.load, onState: (id, s) => (states[id] = s) });
    expect(PORTFOLIO_LEAGUE_CONCURRENCY).toBe(3);
    expect(c.calls).toEqual(["a", "b", "c"]);
    for (const id of ids) {
      await flush();
      c.pending.get(id)?.resolve(response(id));
      await flush();
    }
    expect(c.calls).toEqual(ids);
    expect(c.maxInFlight()).toBeLessThanOrEqual(PORTFOLIO_LEAGUE_CONCURRENCY);
    expect(Object.values(states).every((s) => s.status === "success")).toBe(true);
  });

  it("one failed league does not block the others and can be retried alone", async () => {
    const c = controllable();
    const states: Record<string, PortfolioLeagueState> = {};
    const loader = startLeagueLoader({
      leagueIds: ["a", "b", "c", "d"],
      load: c.load,
      onState: (id, s) => (states[id] = s),
      concurrency: 2,
    });
    c.pending.get("a")?.reject(new Error("boom"));
    await flush();
    expect(states.a).toEqual({ status: "error" });
    expect(c.calls).toEqual(["a", "b", "c"]); // c started in a's slot
    c.pending.get("b")?.resolve(response("b"));
    c.pending.get("c")?.resolve(response("c"));
    await flush();
    c.pending.get("d")?.resolve(response("d"));
    await flush();
    expect(states.b.status).toBe("success");
    expect(states.d.status).toBe("success");

    loader.retry("a");
    expect(states.a).toEqual({ status: "pending" });
    expect(c.calls.filter((id) => id === "a")).toHaveLength(2);
    c.pending.get("a")?.resolve(response("a"));
    await flush();
    expect(states.a.status).toBe("success");
  });

  it("ignores retry for a league that is still loading", () => {
    const c = controllable();
    const loader = startLeagueLoader({ leagueIds: ["a"], load: c.load, onState: vi.fn() });
    loader.retry("a");
    expect(c.calls).toEqual(["a"]);
  });

  it("abort cancels in-flight requests, drops the queue and stops state updates", async () => {
    const c = controllable();
    const onState = vi.fn();
    const loader = startLeagueLoader({ leagueIds: ["a", "b", "c", "d", "e"], load: c.load, onState });
    loader.abort();
    expect(c.signals.get("a")?.aborted).toBe(true);
    c.pending.get("a")?.resolve(response("a"));
    await flush();
    expect(onState).not.toHaveBeenCalled();
    expect(c.calls).toEqual(["a", "b", "c"]);
  });
});

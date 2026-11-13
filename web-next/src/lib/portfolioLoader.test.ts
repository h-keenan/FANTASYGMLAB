import { describe, expect, it, vi } from "vitest";

import type { PortfolioLeagueResponse } from "@/lib/api";
import { PORTFOLIO_EAGER_LEAGUES, PORTFOLIO_LEAGUE_CONCURRENCY, startLeagueLoader } from "@/lib/portfolioLoader";
import type { PortfolioLeagueState } from "@/lib/portfolioProgress";

function response(id: string, signalsPending = false): PortfolioLeagueResponse {
  return {
    ok: true,
    is_premium: true,
    lens: "Dynasty",
    league: null,
    failed_league: null,
    upsell: null,
    _id: id,
    ...(signalsPending ? { signals_pending: true } : {}),
  } as never;
}

/** A load() whose promises the test resolves/rejects by hand. */
function controllable() {
  const calls: string[] = [];
  const phases: string[] = [];
  const pending = new Map<string, { resolve: (v: PortfolioLeagueResponse) => void; reject: (e: unknown) => void }>();
  let inFlight = 0;
  let maxInFlight = 0;
  const signals = new Map<string, AbortSignal>();
  const load = (id: string, signal: AbortSignal, phase: string = "headline") => {
    calls.push(id);
    phases.push(`${id}:${phase}`);
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
  return { load, calls, phases, pending, signals, maxInFlight: () => maxInFlight };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("startLeagueLoader", () => {
  it("starts leagues in saved order and never exceeds the concurrency cap", async () => {
    const c = controllable();
    const ids = ["a", "b", "c", "d", "e", "f", "g"];
    const states: Record<string, PortfolioLeagueState> = {};
    startLeagueLoader({ leagueIds: ids, load: c.load, onState: (id, s) => (states[id] = s), eager: 99 });
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
      eager: 99,
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

  it("loads only the eager window until unlocked, then releases leagues in saved order", async () => {
    const c = controllable();
    const ids = Array.from({ length: 9 }, (_, i) => `l${i}`);
    const loader = startLeagueLoader({ leagueIds: ids, load: c.load, onState: vi.fn(), eager: PORTFOLIO_EAGER_LEAGUES });
    for (let i = 0; i < PORTFOLIO_EAGER_LEAGUES; i += 1) {
      await flush();
      c.pending.get(ids[i])?.resolve(response(ids[i]));
    }
    await flush();
    expect(c.calls).toEqual(ids.slice(0, PORTFOLIO_EAGER_LEAGUES)); // nothing below the window yet
    loader.unlock(2);
    await flush();
    expect(c.calls).toEqual(ids.slice(0, PORTFOLIO_EAGER_LEAGUES + 2));
    loader.unlockAll();
    await flush();
    expect(c.calls).toEqual(ids);
  });

  it("queues every league's headline ahead of any league's full request", async () => {
    const c = controllable();
    const states: Record<string, PortfolioLeagueState> = {};
    startLeagueLoader({
      leagueIds: ["a", "b", "c", "d"],
      load: c.load,
      onState: (id, s) => (states[id] = s),
      concurrency: 2,
      eager: 99,
    });
    expect(c.phases).toEqual(["a:headline", "b:headline"]);
    c.pending.get("a")?.resolve(response("a", true));
    await flush();
    expect(c.phases).toEqual(["a:headline", "b:headline", "c:headline"]); // a's full waits behind c
    c.pending.get("b")?.resolve(response("b", true));
    await flush();
    expect(c.phases.slice(3)).toEqual(["d:headline"]);
    c.pending.get("c")?.resolve(response("c", true));
    c.pending.get("d")?.resolve(response("d", true));
    await flush();
    expect(c.phases.slice(4)).toEqual(["a:full", "b:full"]);
    expect(states.a.status === "success" && states.a.data.signals_pending).toBe(true); // headline painted
    c.pending.get("a")?.resolve(response("a"));
    await flush();
    expect(states.a.status === "success" && states.a.data.signals_pending).toBeFalsy(); // signals filled in
    expect(c.phases.slice(6)).toEqual(["c:full"]);
  });

  it("a complete headline (server had it cached) is final: no second request", async () => {
    const c = controllable();
    startLeagueLoader({ leagueIds: ["a"], load: c.load, onState: vi.fn() });
    c.pending.get("a")?.resolve(response("a"));
    await flush();
    expect(c.phases).toEqual(["a:headline"]);
  });

  it("revalidates warm leagues with one full request and leaves fresh ones alone", async () => {
    const c = controllable();
    startLeagueLoader({ leagueIds: ["a", "b", "c"], load: c.load, onState: vi.fn(), warm: ["b"], skip: ["c"] });
    expect(c.phases).toEqual(["a:headline", "b:full"]);
  });

  it("a failed revalidation never blanks the stale data on screen", async () => {
    const c = controllable();
    const onState = vi.fn();
    startLeagueLoader({ leagueIds: ["a"], load: c.load, onState, warm: ["a"] });
    c.pending.get("a")?.reject(new Error("offline"));
    await flush();
    expect(onState).not.toHaveBeenCalled();
  });

  it("retry on a window-locked league releases it", async () => {
    const c = controllable();
    const onState = vi.fn();
    const loader = startLeagueLoader({ leagueIds: ["a", "b", "c"], load: c.load, onState, eager: 1 });
    expect(c.calls).toEqual(["a"]);
    loader.retry("c");
    await flush();
    expect(c.calls).toContain("c");
    expect(onState).not.toHaveBeenCalled();
  });
});

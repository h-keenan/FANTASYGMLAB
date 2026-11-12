import { beforeEach, describe, expect, it } from "vitest";

import { clearRequestCache, coalesceRead, isCacheablePath, REFERENCE_TTL_MS } from "./requestCache";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("requestCache", () => {
  beforeEach(() => clearRequestCache());

  it("sends one request for concurrent identical reads and hands each caller its own copy", async () => {
    const d = deferred<{ rows: number[] }>();
    let calls = 0;
    const load = () => {
      calls += 1;
      return d.promise;
    };
    const a = coalesceRead("k", false, load);
    const b = coalesceRead("k", false, load);
    d.resolve({ rows: [1, 2] });
    const [ra, rb] = await Promise.all([a, b]);
    expect(calls).toBe(1);
    expect(ra).toEqual({ rows: [1, 2] });
    expect(rb).toEqual({ rows: [1, 2] });
    expect(ra).not.toBe(rb);
  });

  it("does not reuse a result for non-reusable keys once the request has settled", async () => {
    let calls = 0;
    const load = async () => ++calls;
    expect(await coalesceRead("k", false, load)).toBe(1);
    expect(await coalesceRead("k", false, load)).toBe(2);
  });

  it("reuses a reference read inside the TTL, with a fresh copy each time, and reloads after it", async () => {
    let calls = 0;
    let clock = 1_000;
    const now = () => clock;
    const load = async () => ({ n: ++calls });
    const first = await coalesceRead("r", true, load, now);
    first.n = 99; // a consumer mutating its copy must not poison the cache
    clock += REFERENCE_TTL_MS - 1;
    expect(await coalesceRead("r", true, load, now)).toEqual({ n: 1 });
    clock += 2;
    expect(await coalesceRead("r", true, load, now)).toEqual({ n: 2 });
    expect(calls).toBe(2);
  });

  it("drops reused reads when a write clears the cache, including one already in flight", async () => {
    let calls = 0;
    const load = async () => ++calls;
    await coalesceRead("r", true, load);
    clearRequestCache();
    expect(await coalesceRead("r", true, load)).toBe(2);

    const d = deferred<number>();
    const slow = coalesceRead("s", true, () => d.promise);
    clearRequestCache();
    d.resolve(7);
    await slow;
    expect(await coalesceRead("s", true, async () => 8)).toBe(8);
  });

  it("does not cache failures and lets the next caller retry", async () => {
    const d = deferred<number>();
    const a = coalesceRead("e", true, () => d.promise);
    d.reject(new Error("boom"));
    await expect(a).rejects.toThrow("boom");
    expect(await coalesceRead("e", true, async () => 5)).toBe(5);
  });

  it("only allowlists league reference reads", () => {
    expect(isCacheablePath("/v1/leagues/123/rankings?lens=Dynasty&limit=300")).toBe(true);
    expect(isCacheablePath("/v1/leagues/123/draft-picks?lens=Dynasty")).toBe(true);
    expect(isCacheablePath("/v1/leagues/123/rosters")).toBe(true);
    expect(isCacheablePath("/v1/leagues/123/idp/values?include_below=true")).toBe(true);
    expect(isCacheablePath("/v1/leagues/123/dashboard")).toBe(false);
    expect(isCacheablePath("/v1/me")).toBe(false);
    expect(isCacheablePath("/v1/leagues/123/waivers")).toBe(false);
  });
});

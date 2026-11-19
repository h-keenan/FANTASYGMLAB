import { describe, expect, it } from "vitest";

import { BILLING_SLOW_MESSAGE, BILLING_STATUS_UNKNOWN_MESSAGE, SLOW_REQUEST_MESSAGE } from "./badDayCopy";
import { CLIENT_TIMEOUT_CODE, isPostgrestRead, withReadTimeout } from "./requestTimeouts";

const REST = "https://x.supabase.co/rest/v1/saved_leagues?select=*";
const hang: typeof fetch = (_input, init) =>
  new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });

describe("withReadTimeout", () => {
  it("turns a hung PostgREST read into a 408 with the slow copy", async () => {
    const f = withReadTimeout(hang, { message: SLOW_REQUEST_MESSAGE, timeoutMs: 20 });
    const res = await f(REST);
    expect(res.status).toBe(408);
    expect(await res.json()).toEqual({ message: SLOW_REQUEST_MESSAGE, code: CLIENT_TIMEOUT_CODE });
  });

  it("passes a fast read through untouched", async () => {
    const ok: typeof fetch = async () => new Response("[]", { status: 200 });
    const res = await withReadTimeout(ok, { message: "m", timeoutMs: 20 })(REST);
    expect(res.status).toBe(200);
  });

  it("never times out writes or non-PostgREST calls", async () => {
    let seen: AbortSignal | null | undefined = null;
    const spy: typeof fetch = async (_i, init) => {
      seen = init?.signal;
      return new Response("{}");
    };
    const f = withReadTimeout(spy, { message: "m", timeoutMs: 20 });
    await f(REST, { method: "PATCH" });
    expect(seen).toBeUndefined();
    seen = null;
    await f("https://x.supabase.co/auth/v1/token");
    expect(seen).toBeUndefined();
    expect(isPostgrestRead(REST, { method: "POST" })).toBe(false);
    expect(isPostgrestRead(REST, { method: "HEAD" })).toBe(true);
  });

  it("lets a caller abort through as an error, not a timeout", async () => {
    const caller = new AbortController();
    const p = withReadTimeout(hang, { message: "m", timeoutMs: 1000 })(REST, { signal: caller.signal });
    caller.abort();
    await expect(p).rejects.toThrow();
  });

  it("is inert when the kill switch is off", async () => {
    let seen: AbortSignal | null | undefined = null;
    const spy: typeof fetch = async (_i, init) => {
      seen = init?.signal;
      return new Response("[]");
    };
    await withReadTimeout(spy, { message: "m", timeoutMs: 20, enabled: false })(REST);
    expect(seen).toBeUndefined();
  });
});

describe("timeout copy", () => {
  it("billing write copy says the outcome is unknown and never claims failure or success", () => {
    expect(BILLING_STATUS_UNKNOWN_MESSAGE).toMatch(/cannot say whether/);
    expect(BILLING_STATUS_UNKNOWN_MESSAGE).not.toMatch(/failed|did not go through|succeeded|complete/i);
    expect(BILLING_SLOW_MESSAGE).not.toMatch(/failed|charged/i);
  });
});

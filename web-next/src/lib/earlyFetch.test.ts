import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { env } from "./env";
import {
  buildEarlyFetchScript,
  EARLY_FETCH_GLOBAL,
  EARLY_FETCH_TTL_MS,
  earlyOrFetch,
  takeEarlyFetch,
  type EarlyFetch,
} from "./earlyFetch";
import { storageKey } from "./supabaseKeys";

const getSession = vi.fn();
const TOKEN = "header.payload.signature-SECRET";
const API = "https://api.example.test";
const DASH = (lens = "Dynasty") => `${API}/v1/leagues/L1/dashboard?lens=${lens}&defer_trade_ideas=true`;

function session(overrides: Record<string, unknown> = {}) {
  return {
    access_token: TOKEN,
    refresh_token: "r",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3000,
    user: { id: "u1" },
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const holder = () => window as unknown as Record<string, EarlyFetch | undefined>;
function runScript() {
  new Function(buildEarlyFetchScript({ apiBase: API, storageKey }))();
}
function seed(value: unknown) {
  window.localStorage.setItem(storageKey, JSON.stringify(value));
}
function goto(path: string) {
  window.history.pushState({}, "", path);
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  getSession.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.localStorage.clear();
  holder()[EARLY_FETCH_GLOBAL] = undefined;
  goto("/dashboard/L1?name=Test");
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  holder()[EARLY_FETCH_GLOBAL] = undefined;
  goto("/");
});

describe("early-fetch inline script", () => {
  it("starts the dashboard first-paint request with the stored token, to the API origin only", () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    seed(session());
    runScript();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(DASH());
    expect(String(url)).not.toContain(TOKEN);
    expect(init.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    // Only the in-flight request is kept on window: no token anywhere on it.
    const early = holder()[EARLY_FETCH_GLOBAL]!;
    expect(early.uid).toBe("u1");
    expect(early.lid).toBe("L1");
    expect(JSON.stringify({ ...early, p: undefined })).not.toContain(TOKEN);
  });

  it("uses the remembered Non-Dynasty lens, like the app's first fetch", () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    seed(session());
    window.localStorage.setItem("fgl.detectedLens.v1", JSON.stringify({ L1: "Non-Dynasty" }));
    runScript();
    expect(fetchMock.mock.calls[0][0]).toBe(DASH("Non-Dynasty"));
  });

  it("writes nothing new to storage and logs nothing", () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    const log = vi.spyOn(console, "log");
    const warn = vi.spyOn(console, "warn");
    const error = vi.spyOn(console, "error");
    seed(session());
    const before = JSON.stringify({ ...window.localStorage });
    runScript();
    expect(JSON.stringify({ ...window.localStorage })).toBe(before);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
    expect(log).not.toHaveBeenCalled();
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it("does not fire without a stored session", () => {
    runScript();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeUndefined();
  });

  it("does not fire for an expired token or one inside the 120 s refresh floor", () => {
    seed(session({ expires_at: Math.floor(Date.now() / 1000) - 5 }));
    runScript();
    seed(session({ expires_at: Math.floor(Date.now() / 1000) + 60 }));
    runScript();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not fire on malformed or incomplete stored sessions", () => {
    window.localStorage.setItem(storageKey, "{not json");
    runScript();
    seed(session({ user: undefined }));
    runScript();
    seed(session({ refresh_token: "" }));
    runScript();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not fire on auth callback URLs (hash or query)", () => {
    seed(session());
    goto("/dashboard/L1#access_token=abc&refresh_token=def&type=recovery");
    runScript();
    goto("/dashboard/L1?code=pkce-code");
    runScript();
    goto("/dashboard/L1?error=access_denied&error_description=x");
    runScript();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("only fires on /dashboard/<league>", () => {
    seed(session());
    for (const path of ["/", "/dashboard", "/matchup/L1", "/dashboard/L1/extra", "/my-team/L1"]) {
      goto(path);
      runScript();
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("drops the unclaimed request after the TTL", () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(jsonResponse({}));
    seed(session());
    runScript();
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeDefined();
    vi.advanceTimersByTime(EARLY_FETCH_TTL_MS + 1);
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeUndefined();
  });

  it("escapes values so a hostile env value cannot close the script element", () => {
    const script = buildEarlyFetchScript({ apiBase: "https://a.test/</script><script>x", storageKey: "k" });
    expect(script).not.toContain("</script>");
  });
});

describe("takeEarlyFetch", () => {
  const entry = (overrides: Partial<EarlyFetch> = {}): EarlyFetch => ({
    url: DASH(),
    uid: "u1",
    lid: "L1",
    p: Promise.resolve(jsonResponse({ ok: true })),
    ...overrides,
  });

  it("hands out the request once, then clears it", () => {
    const e = entry();
    holder()[EARLY_FETCH_GLOBAL] = e;
    expect(takeEarlyFetch(DASH(), "u1")).toBe(e.p);
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeUndefined();
    expect(takeEarlyFetch(DASH(), "u1")).toBeNull();
  });

  it("leaves it in place for an unrelated request (other calls go first)", () => {
    const e = entry();
    holder()[EARLY_FETCH_GLOBAL] = e;
    expect(takeEarlyFetch(`${API}/v1/me`, "u1")).toBeNull();
    expect(holder()[EARLY_FETCH_GLOBAL]).toBe(e);
  });

  it("refuses and drops it when the signed-in user differs", () => {
    holder()[EARLY_FETCH_GLOBAL] = entry();
    expect(takeEarlyFetch(DASH(), "someone-else")).toBeNull();
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeUndefined();
  });

  it("refuses when the league differs from the one fetched", () => {
    holder()[EARLY_FETCH_GLOBAL] = entry({ lid: "L2" });
    expect(takeEarlyFetch(DASH(), "u1")).toBeNull();
  });

  it("refuses without a user id, and on a different lens", () => {
    holder()[EARLY_FETCH_GLOBAL] = entry();
    expect(takeEarlyFetch(DASH(), undefined)).toBeNull();
    holder()[EARLY_FETCH_GLOBAL] = entry();
    expect(takeEarlyFetch(DASH("Non-Dynasty"), "u1")).toBeNull();
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeDefined();
  });
});

describe("earlyOrFetch", () => {
  it("falls back to a normal fetch when the early request rejects or is aborted", async () => {
    const fallback = jsonResponse({ from: "fallback" });
    const rejected = await earlyOrFetch(Promise.reject(new Error("net")), new AbortController().signal, async () => fallback);
    expect(rejected).toBe(fallback);
    const ac = new AbortController();
    ac.abort();
    const aborted = await earlyOrFetch(new Promise<Response>(() => {}), ac.signal, async () => fallback);
    expect(aborted).toBe(fallback);
  });
});

describe("api.getDashboard consuming the early request", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doMock("./supabase", () => ({
      supabase: { auth: { getSession: () => getSession() } },
      peekStoredSession: () => null,
    }));
    getSession.mockResolvedValue({ data: { session: session() } });
  });
  afterEach(() => {
    vi.doUnmock("./supabase");
  });

  async function loadApi() {
    return (await import("./api")).api;
  }

  it("sends exactly one network request and renders the early response", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, from: "early" }));
    seed(session());
    goto("/dashboard/L1");
    // env.apiBaseUrl is what the app targets; the script must be built against the same origin.
    new Function(buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey }))();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const api = await loadApi();
    const body = (await api.getDashboard("L1", "Dynasty", { deferTradeIdeas: true })) as unknown as { from: string };
    expect(body.from).toBe("early");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeUndefined();
    // A second identical call is an ordinary request (the early one is single-use).
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, from: "second" }));
    const again = (await api.getDashboard("L1", "Dynasty", { deferTradeIdeas: true })) as unknown as { from: string };
    expect(again.from).toBe("second");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("ignores the early result and refetches when the session belongs to a different user", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true, from: "other-users-data" }));
    seed(session({ user: { id: "u-old" } }));
    goto("/dashboard/L1");
    new Function(buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey }))();
    getSession.mockResolvedValue({ data: { session: session({ user: { id: "u-new" } }) } });
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true, from: "fresh" }));
    const api = await loadApi();
    const body = (await api.getDashboard("L1", "Dynasty", { deferTradeIdeas: true })) as unknown as { from: string };
    expect(body.from).toBe("fresh");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("refetches when the early request failed, and maps early HTTP errors like any response", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    seed(session());
    goto("/dashboard/L1");
    new Function(buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey }))();
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true, from: "retry" }));
    const api = await loadApi();
    const body = (await api.getDashboard("L1", "Dynasty", { deferTradeIdeas: true })) as unknown as { from: string };
    expect(body.from).toBe("retry");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // A 404 from the early request is an ApiError, same handling as a normal response.
    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "nope" }, 404));
    new Function(buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey }))();
    await expect(api.getDashboard("L1", "Dynasty", { deferTradeIdeas: true })).rejects.toMatchObject({ status: 404 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not reuse the early request for the full (non-deferred) dashboard call", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, from: "x" }));
    seed(session());
    goto("/dashboard/L1");
    new Function(buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey }))();
    const api = await loadApi();
    await api.getDashboard("L1", "Dynasty");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(holder()[EARLY_FETCH_GLOBAL]).toBeDefined();
  });
});

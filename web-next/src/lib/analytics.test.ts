import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { supabase } from "./supabase";

vi.mock("./supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
    },
  },
}));

function mockFetchOk() {
  const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", mockFetch);
  return mockFetch;
}

describe("lib/analytics", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: { session: null },
    } as never);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("mints an anon id once and persists it across calls", async () => {
    mockFetchOk();
    const { getOrCreateAnonId } = await import("./analytics");

    const first = getOrCreateAnonId();
    const second = getOrCreateAnonId();

    expect(first).toMatch(/^anon_[0-9a-f]{16}$/);
    expect(second).toBe(first);
    expect(window.localStorage.getItem("dynastygm_analytics_anon_id")).toBe(first);
  });

  it("reuses an anon id already saved in localStorage from a prior session", async () => {
    mockFetchOk();
    window.localStorage.setItem("dynastygm_analytics_anon_id", "anon_existing1234567");
    const { getOrCreateAnonId } = await import("./analytics");

    expect(getOrCreateAnonId()).toBe("anon_existing1234567");
  });

  it("still returns a usable id when localStorage throws (private browsing / blocked storage)", async () => {
    mockFetchOk();
    const getItemSpy = vi
      .spyOn(window.localStorage.__proto__, "getItem")
      .mockImplementation(() => {
        throw new Error("blocked");
      });
    const setItemSpy = vi
      .spyOn(window.localStorage.__proto__, "setItem")
      .mockImplementation(() => {
        throw new Error("blocked");
      });

    const { getOrCreateAnonId } = await import("./analytics");

    expect(() => getOrCreateAnonId()).not.toThrow();
    expect(getOrCreateAnonId()).toMatch(/^anon_[0-9a-f]{16}$/);

    getItemSpy.mockRestore();
    setItemSpy.mockRestore();
  });

  it("trackPageView posts the real pathname with no per-route mapping", async () => {
    const mockFetch = mockFetchOk();
    const { trackPageView } = await import("./analytics");

    trackPageView("/trade-hub/league-1");
    // postEvent's body-building is synchronous even though the request
    // itself is awaited inside a fire-and-forget async IIFE.
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/v1/analytics/event");
    const body = JSON.parse(init.body as string);
    expect(body.event).toBe("page_view");
    expect(body.props.route).toBe("/trade-hub/league-1");
    expect(body.anon_id).toMatch(/^anon_/);
  });

  it("trackPageView never calls fetch for a blank route", async () => {
    const mockFetch = mockFetchOk();
    const { trackPageView } = await import("./analytics");

    trackPageView("");
    trackPageView("   ");

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("trackFeatureUse sends the exact event name plus a dedupe once_key scoped by leagueId", async () => {
    const mockFetch = mockFetchOk();
    const { trackFeatureUse } = await import("./analytics");

    trackFeatureUse("trade_hub_opened", { leagueId: "league-9" });
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.event).toBe("trade_hub_opened");
    expect(body.props.league_id).toBe("league-9");
    expect(body.once_key).toBe("league-9");
  });

  it("trackFeatureUse omits once_key entirely when dedupe is disabled", async () => {
    const mockFetch = mockFetchOk();
    const { trackFeatureUse } = await import("./analytics");

    trackFeatureUse("pqv_opened", { dedupe: false });
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.event).toBe("pqv_opened");
    expect(body).not.toHaveProperty("once_key");
  });

  it("attaches the caller's Supabase bearer token when a session exists", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: { session: { access_token: "real-token" } },
    } as never);
    const mockFetch = mockFetchOk();
    const { trackPageView } = await import("./analytics");

    trackPageView("/dashboard/league-1");
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const init = mockFetch.mock.calls[0][1];
    expect(init.headers.Authorization).toBe("Bearer real-token");
  });

  it("trackPageView strips id-like path segments", async () => {
    const mockFetch = mockFetchOk();
    const { trackPageView } = await import("./analytics");

    trackPageView("/trade-hub/1234567890123456");
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.props.route).toBe("/trade-hub/:id");
    expect(body.props.platform).toBe("web");
  });

  it("trackUse sends feature_use with feature/action/tier, platform web and no dedupe", async () => {
    const mockFetch = mockFetchOk();
    const { trackUse } = await import("./analytics");

    trackUse("percentile_explorer", "opened", { tier: "pro", props: { item_kind: "rush_yds" } });
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.event).toBe("feature_use");
    expect(body.props).toMatchObject({
      feature: "percentile_explorer",
      action: "opened",
      tier: "pro",
      item_kind: "rush_yds",
      platform: "web",
    });
    expect(body).not.toHaveProperty("once_key");
  });

  it("trackClientError sends a sanitized class and route, de-dupes and rate limits", async () => {
    const mockFetch = mockFetchOk();
    const { trackClientError, resetErrorRateLimit } = await import("./analytics");
    resetErrorRateLimit();

    const err = new TypeError("secret token abc in message");
    trackClientError("application_error", err, { route: "/my-team/1234567890123456?token=abc" });
    trackClientError("application_error", err, { route: "/my-team/1234567890123456" }); // duplicate
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));

    const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
    expect(body.event).toBe("application_error");
    expect(body.props.error_class).toBe("typeerror");
    expect(body.props.route).toBe("/my-team/:id");
    expect(JSON.stringify(body)).not.toContain("secret");
    expect(JSON.stringify(body)).not.toContain("token=abc");

    for (let status = 500; status < 520; status += 1) {
      trackClientError("provider_error", null, { route: `/r${status}`, status });
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
    // 1 (above) + at most 4 more in the same window.
    expect(mockFetch.mock.calls.length).toBeLessThanOrEqual(5);
  });

  it("errorClassOf buckets statuses", async () => {
    const { errorClassOf } = await import("./analytics");
    expect(errorClassOf(null, 0)).toBe("network");
    expect(errorClassOf(null, 503)).toBe("http_5xx");
    expect(errorClassOf({ status: 404 })).toBe("http_404");
    expect(errorClassOf("weird")).toBe("unknown");
  });

  it("never throws when fetch itself rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    const { trackPageView } = await import("./analytics");

    expect(() => trackPageView("/news")).not.toThrow();
  });
});

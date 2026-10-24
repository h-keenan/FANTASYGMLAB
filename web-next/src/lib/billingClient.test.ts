import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import { billingEndpoint, billingRequest } from "./billingClient";
import { DEFAULT_TRIAL_DAYS, fetchPublicTrialDays, trialHeadline } from "./landingTrial";
import { env } from "./env";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("billingClient", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("targets Supabase edge functions by default and the deprecated FastAPI routes on rollback", () => {
    expect(billingEndpoint("billing-plans", "supabase")).toBe(`${env.supabaseUrl}/functions/v1/billing-plans`);
    expect(billingEndpoint("create-checkout-session", "supabase")).toMatch(/\/functions\/v1\/create-checkout-session$/);
    expect(billingEndpoint("billing-portal-session", "fastapi")).toBe(`${env.apiBaseUrl}/v1/billing/portal`);
    expect(billingEndpoint("create-checkout-session", "fastapi")).toBe(`${env.apiBaseUrl}/v1/billing/checkout`);
    expect(billingEndpoint("billing-plans", "fastapi")).toBe(`${env.apiBaseUrl}/v1/billing/plans`);
  });

  it("sends the user JWT as Authorization and the anon key as apikey", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, client_secret: "cs_1" }));
    const out = await billingRequest<{ client_secret: string }>("create-checkout-session", "user-jwt", {
      method: "POST",
      jsonBody: { tier: "pro", interval: "monthly" },
      backend: "supabase",
    });
    expect(out.client_secret).toBe("cs_1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/functions\/v1\/create-checkout-session$/);
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer user-jwt");
    expect(init.headers.apikey).toBe(env.supabaseAnonKey);
    expect(JSON.parse(init.body)).toEqual({ tier: "pro", interval: "monthly" });
  });

  it("does not send apikey on the FastAPI rollback path", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await billingRequest("billing-plans", "user-jwt", { backend: "fastapi" });
    expect(fetchMock.mock.calls[0][1].headers.apikey).toBeUndefined();
  });

  it("normalizes edge-function {error}, FastAPI {detail} and gateway {msg} into ApiError", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: false, error: "No billing account found for this user yet." }, 404));
    await expect(billingRequest("billing-portal-session", "t", { method: "POST", backend: "supabase" })).rejects.toMatchObject({
      status: 404,
      message: "No billing account found for this user yet.",
    });
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "Could not start checkout." }, 502));
    await expect(billingRequest("create-checkout-session", "t", { method: "POST", backend: "fastapi" })).rejects.toBeInstanceOf(ApiError);
    fetchMock.mockResolvedValueOnce(jsonResponse({ msg: "Invalid JWT" }, 401));
    await expect(billingRequest("billing-plans", "t")).rejects.toMatchObject({ status: 401, message: "Invalid JWT" });
  });

  it("maps transport failure to ApiError status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("network"));
    await expect(billingRequest("billing-plans", "t")).rejects.toMatchObject({ status: 0 });
  });
});

describe("landingTrial", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://proj.supabase.test");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon-key");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("formats the headline from days", () => {
    expect(trialHeadline(DEFAULT_TRIAL_DAYS)).toBe("Start free for 3 days");
    expect(trialHeadline(1)).toBe("Start free for 1 day");
    expect(trialHeadline(0)).toBe("Start free");
  });

  it("reads trial_days from the public plans function with only the anon key", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, trial_days: 7 }));
    expect(await fetchPublicTrialDays()).toBe(7);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://proj.supabase.test/functions/v1/billing-plans");
    expect(init.headers.apikey).toBe("anon-key");
  });

  it("returns null on failure or junk so callers keep the fallback", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 500));
    expect(await fetchPublicTrialDays()).toBeNull();
    fetchMock.mockResolvedValueOnce(jsonResponse({ trial_days: "x" }));
    expect(await fetchPublicTrialDays()).toBeNull();
    fetchMock.mockRejectedValueOnce(new Error("down"));
    expect(await fetchPublicTrialDays()).toBeNull();
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { supabase } from "./supabase";
import { captureAttribution, getAttributionProps, nextFirstTouch, nextLastTouch, parseAttribution } from "./attribution";
import { isTryTopic, TRY_CTA_LABEL, TRY_TOPICS, tryCtaHref, tryTopicInfo } from "./tryLinks";

vi.mock("./supabase", () => ({ supabase: { auth: { getSession: vi.fn() } } }));

const AD_SEARCH = "?utm_source=ad_app&utm_medium=paid_social&utm_campaign=start_sit_hook&utm_content=vid_12&utm_term=flex&fbclid=AbC_123-x";

describe("try topics", () => {
  it("has the five stable, short, shareable paths", () => {
    expect(TRY_TOPICS.map((t) => t.path)).toEqual(["/try/start-sit", "/try/trade", "/try/waivers", "/try/playoffs", "/try/dynasty-values"]);
    for (const t of TRY_TOPICS) {
      expect(t.path).toBe(`/try/${t.topic}`);
      expect(isTryTopic(t.topic)).toBe(true);
      expect(tryTopicInfo(t.topic).path).toBe(t.path);
    }
    expect(isTryTopic("nope")).toBe(false);
    expect(TRY_CTA_LABEL).toBe("Do this for your league");
  });
});

describe("tryCtaHref", () => {
  it("re-attaches the visitor's campaign params and click id to connect-league, unchanged", () => {
    const href = tryCtaHref("trade", AD_SEARCH);
    expect(href.startsWith("/connect-league?")).toBe(true);
    const out = new URLSearchParams(href.split("?")[1]);
    expect(Object.fromEntries(out)).toEqual({
      utm_source: "ad_app",
      utm_medium: "paid_social",
      utm_campaign: "start_sit_hook",
      utm_content: "vid_12",
      utm_term: "flex",
      fbclid: "AbC_123-x",
    });
  });

  it("drops unrelated params and tags an organic visit as site_cta (which never displaces a real touch)", () => {
    const href = tryCtaHref("dynasty-values", "?foo=bar&name=Secret");
    expect(href).toBe("/connect-league?utm_source=try&utm_medium=site_cta&utm_campaign=dynasty_values&utm_content=try_cta");
    expect(href).not.toContain("Secret");
  });

  it("keeps a referral code even without campaign params", () => {
    expect(tryCtaHref("waivers", "?ref=friend_1")).toContain("&ref=friend_1");
    expect(tryCtaHref("waivers", "?utm_source=ad_app&ref=friend_1")).toBe("/connect-league?utm_source=ad_app&ref=friend_1");
  });
});

describe("campaign attribution survives try link -> auth -> onboarding -> first league", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.pushState({}, "", "/");
    vi.mocked(supabase.auth.getSession).mockResolvedValue({ data: { session: null } } as never);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("pure rule: the CTA hop to connect-league keeps the same first and last touch", () => {
    const landing = parseAttribution(AD_SEARCH, "https://l.facebook.com/", "app.fantasygmlab.com");
    const cta = parseAttribution(`?${tryCtaHref("start-sit", AD_SEARCH).split("?")[1]}`, "", "app.fantasygmlab.com");
    expect(cta).toMatchObject({ utm_source: "ad_app", utm_campaign: "start_sit_hook", utm_content: "vid_12", click_id: "fbclid", click_id_value: "AbC_123-x" });
    const first = nextFirstTouch(null, landing);
    const last = nextLastTouch(null, landing);
    expect(nextFirstTouch(first, cta)).toMatchObject({ utm_campaign: "start_sit_hook", click_id_value: "AbC_123-x" });
    expect(nextLastTouch(last, cta)).toMatchObject({ utm_campaign: "start_sit_hook" });
    // an organic CTA (site_cta) never overwrites the ad touch
    const organic = parseAttribution(`?${tryCtaHref("start-sit", "").split("?")[1]}`, "", "app.fantasygmlab.com");
    expect(nextFirstTouch(first, organic)).toBe(first);
    expect(nextLastTouch(last, organic)).toBe(last);
  });

  it("stored touch rides every later event (auth, onboarding, first league) after the query string is gone", async () => {
    // 1. ad click lands on the try page, RouteAnalytics captures it
    window.history.pushState({}, "", `/try/start-sit${AD_SEARCH}`);
    captureAttribution();
    // 2. CTA click -> /connect-league with the carried params (same touch again), then the auth redirect drops the query
    window.history.pushState({}, "", tryCtaHref("start-sit", window.location.search));
    captureAttribution();
    window.history.pushState({}, "", "/auth");
    captureAttribution();
    window.history.pushState({}, "", "/onboarding");
    captureAttribution();
    // 3. downstream events: signup, onboarding, first league
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", mockFetch);
    const { trackFeatureUse } = await import("./analytics");
    for (const name of ["signup_completed", "onboarding_step_completed", "league_connected"]) {
      trackFeatureUse(name, { dedupe: false });
    }
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(3));
    for (const call of mockFetch.mock.calls) {
      const body = JSON.parse(call[1].body as string);
      expect(body.props).toMatchObject({
        utm_source: "ad_app",
        utm_medium: "paid_social",
        utm_campaign: "start_sit_hook",
        utm_content: "vid_12",
        click_id: "fbclid",
        click_id_value: "AbC_123-x",
        lt_utm_campaign: "start_sit_hook",
      });
    }
    expect(getAttributionProps()).toMatchObject({ utm_campaign: "start_sit_hook", lt_utm_source: "ad_app" });
  });

  it("an organic try visit never overwrites an earlier ad touch", async () => {
    window.history.pushState({}, "", `/try/trade${AD_SEARCH}`);
    captureAttribution();
    window.history.pushState({}, "", "/try/waivers");
    captureAttribution();
    window.history.pushState({}, "", tryCtaHref("waivers", ""));
    captureAttribution();
    expect(getAttributionProps()).toMatchObject({ utm_source: "ad_app", utm_campaign: "start_sit_hook", lt_utm_campaign: "start_sit_hook" });
  });

  it("try_link events are demo events: sent only through trackTryLink, with topic and demo=true", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", mockFetch);
    window.history.pushState({}, "", `/try/trade${AD_SEARCH}`);
    captureAttribution();
    const { trackTryLink, trackFeatureUse } = await import("./analytics");
    trackFeatureUse("trade_analyzer_result", { dedupe: false }); // any other event on a /try page stays silent
    trackTryLink("viewed", "trade");
    trackTryLink("viewed", "trade"); // once per session
    trackTryLink("cta_click", "trade");
    await vi.waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    const bodies = mockFetch.mock.calls.map((c) => JSON.parse(c[1].body as string));
    expect(bodies.map((b) => b.props.action)).toEqual(["viewed", "cta_click"]);
    for (const b of bodies) {
      expect(b.event).toBe("feature_use");
      expect(b.props).toMatchObject({ feature: "try_link", item_kind: "trade", demo: true, utm_campaign: "start_sit_hook" });
    }
  });
});

import { afterEach, describe, expect, it } from "vitest";

import {
  captureAttribution,
  clearPendingReferralCode,
  getAttributionProps,
  isStrongTouch,
  nextFirstTouch,
  nextLastTouch,
  getPendingReferralCode,
  parseAttribution,
  referrerHost,
} from "./attribution";

describe("parseAttribution", () => {
  it("reads utm params, click id kind and ref", () => {
    const out = parseAttribution("?utm_source=Reddit&utm_medium=cpc&utm_campaign=Fall-26&gclid=abc&ref=ABC123", "", "app.x.com");
    expect(out).toEqual({
      utm_source: "reddit",
      utm_medium: "cpc",
      utm_campaign: "fall-26",
      click_id: "gclid",
      click_id_value: "abc",
      ref: "ABC123",
      has_ref: true,
    });
  });

  it("keeps utm_content/utm_term and the case-sensitive click id value", () => {
    const out = parseAttribution("?utm_content=Video-A&utm_term=dynasty+trade&fbclid=IwAR_Abc-12&gclid=", "", "x");
    expect(out.utm_content).toBe("video-a");
    expect(out.utm_term).toBe("dynastytrade");
    expect(out.click_id).toBe("fbclid");
    expect(out.click_id_value).toBe("IwAR_Abc-12");
    expect(parseAttribution("?gclid=<b>EAIa", "", "x").click_id_value).toBe("bEAIa");
    expect(parseAttribution("?gbraid=zzz", "", "x").click_id).toBe("gbraid");
  });

  it("drops junk characters and same-site referrers", () => {
    expect(parseAttribution("?utm_source=a b<script>", "", "x").utm_source).toBe("abscript");
    expect(referrerHost("https://app.x.com/a", "app.x.com")).toBe("");
    expect(referrerHost("https://www.reddit.com/r/dynasty", "app.x.com")).toBe("reddit.com");
    expect(referrerHost("not a url", "x")).toBe("");
  });
});

describe("captureAttribution", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("keeps first touch and a pending ref until cleared", () => {
    window.history.replaceState({}, "", "/?utm_source=first&ref=CODE9");
    captureAttribution();
    window.history.replaceState({}, "", "/?utm_source=second");
    captureAttribution();
    expect(getAttributionProps().utm_source).toBe("first");
    expect(getPendingReferralCode()).toBe("CODE9");
    clearPendingReferralCode();
    expect(getPendingReferralCode()).toBe("");
  });
});

describe("first/last touch rules", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("classifies strong vs referrer-only touches", () => {
    expect(isStrongTouch({ utm_source: "x" })).toBe(true);
    expect(isStrongTouch({ click_id: "fbclid" })).toBe(true);
    expect(isStrongTouch({ referrer_host: "instagram.com" })).toBe(false);
    expect(isStrongTouch({ has_ref: true })).toBe(false);
    expect(isStrongTouch(null)).toBe(false);
  });

  it("a referrer-only first touch is upgraded by a later UTM/click-id touch, never the reverse", () => {
    const weak = { referrer_host: "instagram.com" };
    const strong = { utm_source: "meta", utm_campaign: "fall", click_id: "fbclid", click_id_value: "Ab1" };
    expect(nextFirstTouch(weak, strong)).toEqual(strong);
    expect(nextFirstTouch(strong, weak)).toEqual(strong);
    expect(nextFirstTouch({ utm_source: "a" }, { utm_source: "b" })).toEqual({ utm_source: "a" });
  });

  it("last touch keeps the latest campaign touch and ignores a later plain referrer", () => {
    expect(nextLastTouch({ utm_source: "a" }, { utm_source: "b" })).toEqual({ utm_source: "b" });
    expect(nextLastTouch({ utm_source: "a" }, { referrer_host: "x.com" })).toEqual({ utm_source: "a" });
    expect(nextLastTouch({ referrer_host: "x.com" }, { referrer_host: "y.com" })).toEqual({ referrer_host: "y.com" });
  });

  it("our own site_cta links fill an empty slot but never displace a real touch", () => {
    const cta = { utm_source: "player_page", utm_medium: "site_cta", utm_campaign: "seo" };
    const paid = { utm_source: "meta", utm_medium: "paid" };
    expect(nextFirstTouch(null, cta)).toEqual(cta);
    expect(nextLastTouch(null, cta)).toEqual(cta);
    expect(nextFirstTouch(paid, cta)).toEqual(paid);
    expect(nextLastTouch(paid, cta)).toEqual(paid);
    expect(nextFirstTouch({ referrer_host: "google.com" }, cta)).toEqual({ referrer_host: "google.com" });
    expect(nextLastTouch({ referrer_host: "google.com" }, cta)).toEqual({ referrer_host: "google.com" });
  });

  it("persists both and exposes lt_* props without the click id value", () => {
    window.history.replaceState({}, "", "/");
    Object.defineProperty(document, "referrer", { value: "https://www.instagram.com/", configurable: true });
    captureAttribution();
    Object.defineProperty(document, "referrer", { value: "", configurable: true });
    window.history.replaceState({}, "", "/?utm_source=meta&utm_campaign=fall&fbclid=Ab1");
    captureAttribution();
    window.history.replaceState({}, "", "/?utm_source=tiktok");
    captureAttribution();
    const props = getAttributionProps();
    expect(props.utm_source).toBe("meta"); // first strong touch
    expect(props.click_id).toBe("fbclid"); // upgraded from the referrer-only first touch
    expect(props.lt_utm_source).toBe("tiktok"); // last touch
    expect(props).not.toHaveProperty("lt_click_id_value");
  });
});

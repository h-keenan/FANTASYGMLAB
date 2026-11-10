import { afterEach, describe, expect, it } from "vitest";

import {
  captureAttribution,
  clearPendingReferralCode,
  getAttributionProps,
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

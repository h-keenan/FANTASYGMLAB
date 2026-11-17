import { describe, expect, it } from "vitest";

import * as copy from "./accountDeletionCopy";

describe("accountDeletionCopy", () => {
  it("tells App Store subscribers to cancel in iOS Settings and links there", () => {
    expect(copy.DELETE_ACCOUNT_APP_STORE_NOTE).toMatch(/iOS Settings/);
    expect(copy.DELETE_ACCOUNT_APP_STORE_NOTE).toMatch(/Subscriptions/);
    expect(copy.APP_STORE_SUBSCRIPTIONS_URL).toMatch(/apps\.apple\.com\/account\/subscriptions$/);
  });
  it("has no em-dashes", () => {
    for (const v of Object.values(copy)) expect(String(v)).not.toContain("—");
  });
});

import { describe, expect, it } from "vitest";

import { isShareCardVisit, LANDING_SHARE_ATTR, LANDING_SHARE_SCRIPT } from "./landingShare";
import { LANDING_ROOT_ID } from "./landingPending";

describe("landing share-card flag", () => {
  it("matches only utm_campaign=share_card", () => {
    expect(isShareCardVisit("?utm_source=share&utm_medium=qr&utm_campaign=share_card")).toBe(true);
    expect(isShareCardVisit("?utm_campaign=other")).toBe(false);
    expect(isShareCardVisit("")).toBe(false);
  });

  it("inline script flags the root for the share URL and leaves it alone otherwise", () => {
    const run = (url: string) => {
      window.history.replaceState({}, "", url);
      document.body.innerHTML = `<div id="${LANDING_ROOT_ID}"></div>`;
      new Function(LANDING_SHARE_SCRIPT)();
      return document.getElementById(LANDING_ROOT_ID)!;
    };
    expect(run("/?utm_source=share&utm_medium=qr&utm_campaign=share_card")).toHaveAttribute(LANDING_SHARE_ATTR);
    expect(run("/")).not.toHaveAttribute(LANDING_SHARE_ATTR);
    window.history.replaceState({}, "", "/");
  });
});

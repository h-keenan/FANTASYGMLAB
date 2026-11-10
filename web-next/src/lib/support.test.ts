import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { HELP_LINK_LABEL, SUPPORT_EMAIL, supportMailto } from "./support";

describe("support help entry", () => {
  it("builds a mailto with the topic, platform and league id prefilled", () => {
    const href = supportMailto({ topic: "connect_error", platform: "sleeper", leagueId: "123", detail: "No leagues" });
    expect(href.startsWith(`mailto:${SUPPORT_EMAIL}?subject=`)).toBe(true);
    const body = decodeURIComponent(href.split("body=")[1]);
    expect(body).toContain("Where: connect_error");
    expect(body).toContain("Platform: sleeper");
    expect(body).toContain("League id: 123");
    expect(body).toContain("Message: No leagues");
  });

  it("keeps the address and label identical on mobile", () => {
    const mobile = readFileSync(path.join(__dirname, "../../../mobile/src/lib/support.ts"), "utf8");
    expect(mobile).toContain(`export const SUPPORT_EMAIL = "${SUPPORT_EMAIL}";`);
    expect(mobile).toContain(`export const HELP_LINK_LABEL = "${HELP_LINK_LABEL}";`);
  });
});

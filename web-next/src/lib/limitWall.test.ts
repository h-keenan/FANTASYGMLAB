import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { formatLimitReset, LIMIT_WALL_REASONS, limitWallForReason } from "./limitWall";

describe("limitWallForReason", () => {
  it("builds the weekly wall from the server's number and reset", () => {
    const m = limitWallForReason("weekly_limit_reached", {
      info: { limit: 3, window: "week", resets_at: "2026-11-02T00:00:00+00:00" },
      timeZone: "UTC",
    });
    expect(m?.title).toBe("You've used your 3 free trade checks this week");
    expect(m?.body).toContain("Monday, Nov 2, 12:00 AM");
    expect(m?.proLine).toMatch(/Pro/);
    expect(m?.cta).toBe("upgrade");
    expect(m?.ctaLabel).toBe("Upgrade to Pro");
  });

  it("never invents a number or time the server did not send", () => {
    const m = limitWallForReason("weekly_limit_reached");
    expect(m?.title).not.toMatch(/\d/);
    expect(m?.body).not.toMatch(/\d/);
  });

  it("asks guests to create an account instead of buying", () => {
    const m = limitWallForReason("weekly_limit_reached", { isGuest: true });
    expect(m?.cta).toBe("create_account");
    expect(m?.ctaLabel).toBe("Create an account");
  });

  it("covers every exported reason and ignores others", () => {
    for (const r of LIMIT_WALL_REASONS) expect(limitWallForReason(r)).not.toBeNull();
    expect(limitWallForReason("no_player_data")).toBeNull();
    expect(limitWallForReason("")).toBeNull();
    expect(limitWallForReason(undefined)).toBeNull();
  });

  it("formatLimitReset tolerates bad input", () => {
    expect(formatLimitReset("nope")).toBe("");
    expect(formatLimitReset(null)).toBe("");
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "limitWall.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/limitWall.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { freeLimitNote } from "./freeLimits";

describe("freeLimitNote", () => {
  it("shows used-of-limit for a saved cap, before the wall", () => {
    const note = freeLimitNote({ kind: "cap", noun: "GM Targets", limit: 3, used: 2, isPremium: false });
    expect(note).toMatchObject({ text: "Free: 2 of 3 GM Targets", atLimit: false, cta: "upgrade", ctaLabel: "Upgrade" });
  });

  it("flags the limit when reached", () => {
    expect(freeLimitNote({ kind: "cap", noun: "league", limit: 1, used: 1, isPremium: false })?.atLimit).toBe(true);
  });

  it("describes a truncated list honestly, using what is actually shown", () => {
    const note = freeLimitNote({ kind: "window", noun: "trade ideas", limit: 2, total: 7, shown: 2, isPremium: false });
    expect(note?.text).toBe("Free: showing 2 of 7 trade ideas");
    expect(note?.atLimit).toBe(true);
    const unlocked = freeLimitNote({ kind: "window", noun: "trade ideas", limit: 2, total: 7, shown: 4, isPremium: false });
    expect(unlocked?.text).toBe("Free: showing 4 of 7 trade ideas");
  });

  it("says 'up to N' when nothing is hidden yet", () => {
    const note = freeLimitNote({ kind: "window", noun: "next moves", limit: 4, total: 3, shown: 3, isPremium: false });
    expect(note).toMatchObject({ text: "Free: up to 4 next moves", atLimit: false });
  });

  it("sends guests to create an account first (guests may not buy)", () => {
    const note = freeLimitNote({ kind: "cap", noun: "GM Targets", limit: 3, used: 0, isPremium: false, isGuest: true });
    expect(note).toMatchObject({ cta: "create_account", ctaLabel: "Create an account" });
  });

  it("stays silent for Premium, unknown plans and missing or invalid limits", () => {
    expect(freeLimitNote({ kind: "cap", noun: "x", limit: 3, used: 1, isPremium: true })).toBeNull();
    expect(freeLimitNote({ kind: "cap", noun: "x", limit: 3, used: 1, isPremium: null })).toBeNull();
    expect(freeLimitNote({ kind: "cap", noun: "x", limit: 3, used: 1, isPremium: undefined })).toBeNull();
    expect(freeLimitNote({ kind: "cap", noun: "x", limit: undefined, used: 1, isPremium: false })).toBeNull();
    expect(freeLimitNote({ kind: "cap", noun: "x", limit: 0, used: 1, isPremium: false })).toBeNull();
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "freeLimits.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/freeLimits.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});

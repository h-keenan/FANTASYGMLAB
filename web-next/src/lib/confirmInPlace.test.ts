import { describe, expect, it } from "vitest";

import { ASK_REVERT_MS, TAP_AGAIN_REVERT_MS, confirmAnnouncement, reduceConfirm, revertMs } from "./confirmInPlace";

describe("reduceConfirm", () => {
  it("arms, confirms and finishes", () => {
    expect(reduceConfirm("idle", "arm")).toBe("armed");
    expect(reduceConfirm("armed", "confirm")).toBe("busy");
    expect(reduceConfirm("busy", "succeeded")).toBe("idle");
  });
  it("lands in error on failure and can retry or cancel", () => {
    expect(reduceConfirm("busy", "failed")).toBe("error");
    expect(reduceConfirm("error", "confirm")).toBe("busy");
    expect(reduceConfirm("error", "cancel")).toBe("idle");
  });
  it("cancel and timeout revert an armed control but never a running request", () => {
    expect(reduceConfirm("armed", "cancel")).toBe("idle");
    expect(reduceConfirm("armed", "timeout")).toBe("idle");
    expect(reduceConfirm("busy", "cancel")).toBe("busy");
    expect(reduceConfirm("busy", "timeout")).toBe("busy");
  });
  it("ignores a confirm while idle (no accidental one-tap action)", () => {
    expect(reduceConfirm("idle", "confirm")).toBe("idle");
  });
  it("uses a 4 s revert for tap-again and a longer one for ask", () => {
    expect(revertMs("tap-again")).toBe(TAP_AGAIN_REVERT_MS);
    expect(TAP_AGAIN_REVERT_MS).toBe(4000);
    expect(revertMs("ask")).toBe(ASK_REVERT_MS);
  });
  it("announces each phase", () => {
    const copy = { label: "Sign out", prompt: "Delete this game?", confirmLabel: "Delete", keepLabel: "Keep" };
    expect(confirmAnnouncement("armed", "tap-again", copy)).toContain("Tap again to confirm");
    expect(confirmAnnouncement("armed", "ask", copy)).toBe("Delete this game? Delete or Keep.");
    expect(confirmAnnouncement("idle", "ask", copy)).toBe("");
    expect(confirmAnnouncement("error", "ask", { ...copy, errorText: "Nope" })).toBe("Nope");
  });
});

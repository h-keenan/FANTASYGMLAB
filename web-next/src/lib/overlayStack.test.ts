import { describe, expect, it, vi } from "vitest";

import { OVERLAY_Z, createOverlayStack, planHistorySync, type OverlayEntry } from "./overlayStack";

const entry = (id: string, kind: OverlayEntry["kind"] = "sheet", title = id, dismiss: () => void = () => {}): OverlayEntry => ({ id, kind, title, dismiss });

describe("overlayStack: one pop-up at a time", () => {
  it("shows only the newest sheet; opening another replaces it on screen, keeping the first mounted", () => {
    const s = createOverlayStack();
    s.open(entry("a"));
    s.open(entry("b"));
    expect(s.topSheet()?.id).toBe("b");
    expect(s.isHidden("a")).toBe(true);
    expect(s.isHidden("b")).toBe(false);
    expect(s.size()).toBe(2);
  });

  it("closing the top returns to the previous sheet", () => {
    const s = createOverlayStack();
    s.open(entry("a"));
    s.open(entry("b"));
    s.close("b");
    expect(s.topSheet()?.id).toBe("a");
    expect(s.isHidden("a")).toBe(false);
  });

  it("the newer sheet knows what to go back to (the Back label)", () => {
    const s = createOverlayStack();
    s.open(entry("picker", "sheet", "Trade picker"));
    s.open(entry("pqv", "sheet", "Player card"));
    expect(s.previousSheet("pqv")?.title).toBe("Trade picker");
    expect(s.previousSheet("picker")).toBeNull();
  });

  it("a dialog sits on top without hiding the sheet, and closing it returns to the sheet", () => {
    const s = createOverlayStack();
    s.open(entry("sheet"));
    s.open(entry("signout", "dialog"));
    expect(s.isHidden("sheet")).toBe(false);
    expect(s.isHidden("signout")).toBe(false);
    expect(s.isTop("signout")).toBe(true);
    expect(s.layer("signout")).toBeGreaterThan(s.layer("sheet"));
    expect(OVERLAY_Z.toast).toBeGreaterThan(OVERLAY_Z.dialog);
    s.close("signout");
    expect(s.isTop("sheet")).toBe(true);
  });

  it("a dialog never counts as the sheet to go back to", () => {
    const s = createOverlayStack();
    s.open(entry("a", "sheet", "A"));
    s.open(entry("d", "dialog"));
    s.open(entry("b", "sheet", "B"));
    expect(s.previousSheet("b")?.id).toBe("a");
  });

  it("back dismisses only the newest; closeAll dismisses everything, newest first", () => {
    const calls: string[] = [];
    const s = createOverlayStack();
    for (const id of ["a", "b", "c"]) s.open(entry(id, "sheet", id, () => calls.push(id)));
    expect(s.back()?.id).toBe("c");
    expect(calls).toEqual(["c"]);
    expect(s.closeAll()).toEqual(["c", "b", "a"]);
    expect(calls).toEqual(["c", "c", "b", "a"]);
    expect(createOverlayStack().back()).toBeNull();
  });

  it("is idempotent per id, refreshes a changed dismiss, and notifies only on real changes", () => {
    const s = createOverlayStack();
    const listener = vi.fn();
    s.subscribe(listener);
    const dismiss = () => {};
    s.open(entry("a", "sheet", "A", dismiss));
    s.open(entry("a", "sheet", "A", dismiss));
    s.close("zzz");
    expect(listener).toHaveBeenCalledTimes(1);
    const v = s.version();
    s.open(entry("a", "sheet", "A2", dismiss));
    expect(s.version()).toBe(v + 1);
    expect(s.entries()).toHaveLength(1);
    expect(s.entries()[0].title).toBe("A2");
  });
});

describe("planHistorySync", () => {
  it("adds one history entry per newly opened overlay and drops one per closed overlay", () => {
    expect(planHistorySync(0, 1)).toEqual({ push: 1, pop: 0 });
    expect(planHistorySync(1, 2)).toEqual({ push: 1, pop: 0 });
    expect(planHistorySync(2, 0)).toEqual({ push: 0, pop: 2 });
    expect(planHistorySync(1, 1)).toEqual({ push: 0, pop: 0 });
  });
});

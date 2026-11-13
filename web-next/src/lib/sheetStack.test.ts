import { describe, expect, it, vi } from "vitest";

import { createSheetStack } from "./sheetStack";

describe("sheetStack", () => {
  it("shows only the newest sheet and hides the rest", () => {
    const stack = createSheetStack();
    stack.open("a");
    expect(stack.top()).toBe("a");
    expect(stack.isHidden("a")).toBe(false);
    stack.open("b");
    expect(stack.top()).toBe("b");
    expect(stack.isHidden("a")).toBe(true);
    expect(stack.isHidden("b")).toBe(false);
    expect(stack.size()).toBe(2);
  });

  it("restores the previous sheet when the top one closes", () => {
    const stack = createSheetStack();
    stack.open("a");
    stack.open("b");
    stack.close("b");
    expect(stack.top()).toBe("a");
    expect(stack.isHidden("a")).toBe(false);
  });

  it("ignores duplicate opens and unknown closes, and only notifies on real changes", () => {
    const stack = createSheetStack();
    const listener = vi.fn();
    stack.subscribe(listener);
    stack.open("a");
    stack.open("a");
    stack.close("zzz");
    expect(listener).toHaveBeenCalledTimes(1);
    const before = stack.version();
    stack.close("a");
    expect(stack.version()).toBe(before + 1);
    expect(stack.top()).toBeNull();
  });

  it("stops notifying after unsubscribe", () => {
    const stack = createSheetStack();
    const listener = vi.fn();
    const off = stack.subscribe(listener);
    off();
    stack.open("a");
    expect(listener).not.toHaveBeenCalled();
  });
});

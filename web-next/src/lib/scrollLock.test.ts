import { afterEach, describe, expect, it, vi } from "vitest";

import { __resetScrollLock, lockScroll, unlockScroll } from "./scrollLock";

afterEach(() => {
  __resetScrollLock();
  document.body.removeAttribute("style");
  vi.restoreAllMocks();
});

describe("scroll lock", () => {
  it("pins the body at the current scroll offset and restores the exact position", () => {
    Object.defineProperty(window, "scrollY", { value: 1234, configurable: true });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    document.body.style.overflow = "auto";
    lockScroll();
    expect(document.body.style.position).toBe("fixed");
    expect(document.body.style.top).toBe("-1234px");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.hasAttribute("data-overlay-open")).toBe(true);
    unlockScroll();
    expect(document.body.style.position).toBe("");
    expect(document.body.style.top).toBe("");
    expect(document.body.style.overflow).toBe("auto");
    expect(document.body.hasAttribute("data-overlay-open")).toBe(false);
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 1234 }));
  });

  it("is reference counted: nested locks release only on the last unlock", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    lockScroll();
    lockScroll();
    unlockScroll();
    expect(document.body.style.position).toBe("fixed");
    unlockScroll();
    expect(document.body.style.position).toBe("");
  });
});

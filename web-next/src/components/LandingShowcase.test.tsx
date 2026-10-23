import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LandingShowcase, SHOWCASE_RESUME_MS, SHOWCASE_SLIDE_MS } from "./LandingShowcase";

let ioCallback: IntersectionObserverCallback | null = null;
let reducedMotion = false;

function setIntersecting(v: boolean) {
  act(() => {
    ioCallback?.([{ isIntersecting: v } as IntersectionObserverEntry], {} as IntersectionObserver);
  });
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function activeIndex() {
  return Array.from(document.querySelectorAll(".landing-shot")).findIndex(
    (li) => li.getAttribute("data-active") === "true",
  );
}
function section() {
  return document.querySelector(".landing-showcase") as HTMLElement;
}

beforeEach(() => {
  vi.useFakeTimers();
  reducedMotion = false;
  vi.stubGlobal(
    "matchMedia",
    (q: string) =>
      ({
        matches: q.includes("reduce") ? reducedMotion : false,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(cb: IntersectionObserverCallback) {
        ioCallback = cb;
      }
      observe() {}
      disconnect() {}
    },
  );
  HTMLElement.prototype.scrollTo = vi.fn() as unknown as typeof HTMLElement.prototype.scrollTo;
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function start() {
  render(<LandingShowcase />);
  setIntersecting(true);
}

describe("LandingShowcase autoplay", () => {
  it("renders the first slide active and static before autoplay", () => {
    render(<LandingShowcase />);
    expect(activeIndex()).toBe(0);
    expect(section().dataset.playing).toBe("false");
  });

  it("advances on a timer and loops", () => {
    start();
    expect(section().dataset.playing).toBe("true");
    advance(SHOWCASE_SLIDE_MS);
    expect(activeIndex()).toBe(1);
    for (let i = 0; i < 5; i++) advance(SHOWCASE_SLIDE_MS);
    expect(activeIndex()).toBe(0);
  });

  it("pauses on interaction and resumes ~4s after it ends", () => {
    start();
    fireEvent.touchStart(section());
    advance(SHOWCASE_SLIDE_MS * 3);
    expect(activeIndex()).toBe(0);
    expect(section().dataset.playing).toBe("false");
    fireEvent.touchEnd(section());
    advance(SHOWCASE_RESUME_MS);
    expect(section().dataset.playing).toBe("true");
    advance(SHOWCASE_SLIDE_MS);
    expect(activeIndex()).toBe(1);
  });

  it("pause button stops autoplay until pressed again", () => {
    start();
    fireEvent.click(screen.getByRole("button", { name: "Pause slideshow" }));
    advance(SHOWCASE_SLIDE_MS * 3);
    expect(activeIndex()).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Play slideshow" }));
    advance(SHOWCASE_SLIDE_MS);
    expect(activeIndex()).toBe(1);
  });

  it("pauses while off-screen", () => {
    start();
    setIntersecting(false);
    advance(SHOWCASE_SLIDE_MS * 3);
    expect(activeIndex()).toBe(0);
    setIntersecting(true);
    advance(SHOWCASE_SLIDE_MS);
    expect(activeIndex()).toBe(1);
  });

  it("pauses while the tab is hidden", () => {
    start();
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    advance(SHOWCASE_SLIDE_MS * 3);
    expect(activeIndex()).toBe(0);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
  });

  it("does not autoplay under prefers-reduced-motion and hides the pause button", () => {
    reducedMotion = true;
    start();
    advance(SHOWCASE_SLIDE_MS * 3);
    expect(activeIndex()).toBe(0);
    expect(section().dataset.playing).toBe("false");
    expect(screen.queryByRole("button", { name: /slideshow/ })).toBeNull();
  });

  it("dots jump to a slide and reflect the active one", () => {
    start();
    const dots = screen.getAllByRole("button", { name: /^Show / });
    fireEvent.click(dots[3]);
    expect(activeIndex()).toBe(3);
    expect(dots[3].getAttribute("aria-current")).toBe("true");
  });
});

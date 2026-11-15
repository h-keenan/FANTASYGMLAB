import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Collapse, Presence, PresenceList, PresenceSwap } from "@/components/ui/Presence";

function setReducedMotion(on: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({ matches: on && query.includes("reduce"), media: query, addEventListener: () => {}, removeEventListener: () => {} }),
  });
}

describe("Presence", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setReducedMotion(false);
  });
  afterEach(() => {
    vi.useRealTimers();
    // @ts-expect-error test cleanup
    delete window.matchMedia;
  });

  it("enters when shown and keeps the content through its exit, then unmounts", () => {
    const onExited = vi.fn();
    const { rerender } = render(<Presence show={false} variant="rise" testId="p" onExited={onExited}>hello</Presence>);
    expect(screen.queryByTestId("p")).toBeNull();
    rerender(<Presence show variant="rise" testId="p" onExited={onExited}>hello</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entering");
    act(() => vi.advanceTimersByTime(240));
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entered");
    // Hidden: the caller renders nothing, the last children stay on screen while it leaves.
    rerender(<Presence show={false} variant="rise" testId="p" onExited={onExited}>{null}</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "exiting");
    expect(screen.getByTestId("p")).toHaveTextContent("hello");
    act(() => vi.advanceTimersByTime(179));
    expect(screen.getByTestId("p")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(2));
    expect(screen.queryByTestId("p")).toBeNull();
    expect(onExited).toHaveBeenCalledTimes(1);
  });

  it("is simply there on first render unless `appear`", () => {
    const { unmount } = render(<Presence show testId="p">x</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entered");
    unmount();
    render(<Presence show appear testId="p">x</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entering");
  });

  it("clamps durations to 120-300ms", () => {
    render(<Presence show appear enterMs={5} exitMs={9000} testId="p">x</Presence>);
    const style = screen.getByTestId("p").getAttribute("style") ?? "";
    expect(style).toContain("--presence-enter: 120ms");
    expect(style).toContain("--presence-exit: 300ms");
  });

  it("under prefers-reduced-motion it appears and disappears at once (no entering or exiting phase)", () => {
    setReducedMotion(true);
    const { rerender } = render(<Presence show={false} testId="p">x</Presence>);
    rerender(<Presence show testId="p">x</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entered");
    rerender(<Presence show={false} testId="p">{null}</Presence>);
    expect(screen.queryByTestId("p")).toBeNull();
  });

  it("re-showing during the exit reverses it without unmounting", () => {
    const { rerender } = render(<Presence show testId="p">x</Presence>);
    rerender(<Presence show={false} testId="p">x</Presence>);
    act(() => vi.advanceTimersByTime(90));
    rerender(<Presence show testId="p">x</Presence>);
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entering");
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId("p")).toHaveAttribute("data-presence", "entered");
  });

  it("Collapse animates a measured height (px) in, and back to 0 on close; at rest it carries no inline height", () => {
    const { rerender } = render(<Collapse open={false} testId="c"><p>body</p></Collapse>);
    expect(screen.queryByTestId("c")).toBeNull();
    // jsdom has no layout: give the body a height to measure.
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, get: () => 96 });
    rerender(<Collapse open testId="c"><p>body</p></Collapse>);
    const el = screen.getByTestId("c");
    expect(el.style.height).toBe("96px");
    expect(el.style.overflow).toBe("hidden");
    expect(el.style.transition).toContain("height 240ms");
    act(() => vi.advanceTimersByTime(240));
    expect(el.style.height).toBe("");
    expect(el.style.overflow).toBe("");
    rerender(<Collapse open={false} testId="c"><p>body</p></Collapse>);
    expect(el.style.height).toBe("0px");
    expect(el.style.opacity).toBe("0");
    act(() => vi.advanceTimersByTime(180));
    expect(screen.queryByTestId("c")).toBeNull();
    // @ts-expect-error test cleanup
    delete HTMLElement.prototype.scrollHeight;
  });

  it("PresenceList: a removed row plays its exit in place, then goes; an added row enters", () => {
    const rows = (ids: string[]) => <PresenceList items={ids} getKey={(id) => id} render={(id) => <span data-testid={`row-${id}`}>{id}</span>} />;
    const { rerender } = render(rows(["a", "b", "c"]));
    rerender(rows(["a", "c"]));
    expect(screen.getByTestId("row-b")).toBeInTheDocument();
    expect(screen.getByTestId("row-b").parentElement).toHaveAttribute("data-presence", "exiting");
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByTestId("row-b")).toBeNull();
    expect(screen.getByTestId("row-a")).toBeInTheDocument();
    rerender(rows(["a", "d", "c"]));
    expect(screen.getByTestId("row-d").parentElement).toHaveAttribute("data-presence", "entering");
  });

  it("PresenceList: past 24 rows nothing animates (a removed row is gone at once)", () => {
    const ids = Array.from({ length: 30 }, (_, i) => `r${i}`);
    const rows = (list: string[]) => <PresenceList items={list} getKey={(id) => id} render={(id) => <span data-testid={`row-${id}`}>{id}</span>} />;
    const { rerender } = render(rows(ids));
    rerender(rows(ids.slice(1)));
    expect(screen.queryByTestId("row-r0")).toBeNull();
  });

  it("PresenceSwap: the old body fades out, then the new one enters", () => {
    const { rerender } = render(<PresenceSwap swapKey="one"><p>first</p></PresenceSwap>);
    rerender(<PresenceSwap swapKey="two"><p>second</p></PresenceSwap>);
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.queryByText("second")).toBeNull();
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("first")).toBeNull();
    expect(screen.getByText("second")).toBeInTheDocument();
  });
});

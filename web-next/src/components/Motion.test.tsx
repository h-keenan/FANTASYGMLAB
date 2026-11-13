import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Confetti, CountUp, MotionIn, PulseOnIncrease } from "@/components/Motion";
import { useReducedMotion } from "@/lib/useMotion";

type Listener = () => void;

function mockMatchMedia(reduced: boolean) {
  const listeners = new Set<Listener>();
  let matches = reduced;
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("prefers-reduced-motion") ? matches : false,
    media: query,
    addEventListener: (_: string, cb: Listener) => listeners.add(cb),
    removeEventListener: (_: string, cb: Listener) => listeners.delete(cb),
  })) as never;
  return {
    set(next: boolean) {
      matches = next;
      listeners.forEach((cb) => cb());
    },
  };
}

afterEach(() => vi.restoreAllMocks());

describe("reduced-motion switch", () => {
  it("useReducedMotion follows the OS setting, live", () => {
    const mm = mockMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    act(() => mm.set(true));
    expect(result.current).toBe(true);
  });

  it("MotionIn animates by default, never when reduced, and never for long lists", () => {
    mockMatchMedia(false);
    const { rerender, container } = render(<MotionIn index={1} count={4}>row</MotionIn>);
    expect(container.firstElementChild).toHaveClass("motion-in");
    expect(container.firstElementChild).toHaveAttribute("data-motion");
    rerender(<MotionIn index={1} count={25}>row</MotionIn>);
    expect(container.firstElementChild).toHaveAttribute("data-motion", "off"); // over MAX_ANIMATED_ROWS
    expect(container.firstElementChild).not.toHaveClass("motion-in");
    mockMatchMedia(true);
    const reduced = render(<MotionIn index={0} count={3}>row</MotionIn>);
    expect(reduced.container.firstElementChild).toHaveAttribute("data-motion", "off");
    expect(screen.getAllByText("row").length).toBeGreaterThan(0); // content is simply there
  });

  it("CountUp shows the final value at once when reduced; counts from 0 otherwise", () => {
    mockMatchMedia(true);
    const reduced = render(<CountUp value={128.4} />);
    expect(reduced.container).toHaveTextContent("128.4");
    mockMatchMedia(false);
    const normal = render(<CountUp value={128.4} />);
    expect(normal.container).toHaveTextContent("0.0"); // the first frame; it counts up from here
  });

  it("confetti is only for a title and never when reduced", () => {
    mockMatchMedia(false);
    const none = render(<Confetti wonTitle={false} />);
    expect(none.queryByTestId("confetti")).toBeNull();
    none.unmount();
    const title = render(<Confetti wonTitle />);
    expect(title.getByTestId("confetti").children.length).toBeGreaterThan(10);
    title.unmount();
    mockMatchMedia(true);
    expect(render(<Confetti wonTitle />).queryByTestId("confetti")).toBeNull();
  });

  it("a badge pulses when its count goes up, not on first render or when it goes down", () => {
    mockMatchMedia(false);
    const { container, rerender } = render(<PulseOnIncrease value={1}>1</PulseOnIncrease>);
    expect(container.querySelector("[data-pulse]")).toBeNull();
    rerender(<PulseOnIncrease value={2}>2</PulseOnIncrease>);
    expect(container.querySelector("[data-pulse]")).not.toBeNull();
    rerender(<PulseOnIncrease value={1}>1</PulseOnIncrease>);
    expect(container.querySelector(".motion-pulse")).not.toBeNull(); // stays marked until the next change replays it
  });
});

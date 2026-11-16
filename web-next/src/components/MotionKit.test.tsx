import { act, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProgressFill, RankChip, SuccessCheck } from "@/components/Motion";
import { useFlipList } from "@/lib/useFlipList";

function mockMatchMedia(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("prefers-reduced-motion") ? reduced : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as never;
}

beforeEach(() => {
  vi.useFakeTimers();
  mockMatchMedia(false);
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ProgressFill", () => {
  it("grows from 0 to the percent with transform only, and follows changes", () => {
    const { rerender } = render(<ProgressFill percent={60} color="red" testId="fill" />);
    const fill = screen.getByTestId("fill");
    expect(fill.style.transform).toBe("scaleX(0)");
    expect(fill.style.width).toBe("100%");
    act(() => {
      vi.advanceTimersByTime(40);
    });
    expect(fill.style.transform).toBe("scaleX(0.6)");
    rerender(<ProgressFill percent={90} color="red" testId="fill" />);
    act(() => {
      vi.advanceTimersByTime(40);
    });
    expect(fill.style.transform).toBe("scaleX(0.9)");
  });
  it("shows the final width at once under reduced motion", () => {
    mockMatchMedia(true);
    render(<ProgressFill percent={25} color="red" testId="fill" />);
    expect(screen.getByTestId("fill").style.transform).toBe("scaleX(0.25)");
  });
});

describe("RankChip", () => {
  it("is empty on first render, shows up/down when the rank moves, and fades away", () => {
    const { rerender, container } = render(<RankChip rank={5} />);
    expect(container.firstChild).toBeNull();
    rerender(<RankChip rank={3} />);
    const chip = screen.getByRole("status");
    expect(chip).toHaveAttribute("data-dir", "up");
    expect(chip).toHaveAttribute("aria-label", "Up 2");
    rerender(<RankChip rank={4} />);
    expect(screen.getByRole("status")).toHaveAttribute("data-dir", "down");
    act(() => {
      vi.advanceTimersByTime(2600);
    });
    expect(container.firstChild).toBeNull();
  });
});

describe("SuccessCheck", () => {
  it("is a named image with a drawn check path", () => {
    const { container } = render(<SuccessCheck label="Trade accepted" />);
    expect(screen.getByRole("img", { name: "Trade accepted" })).toBeTruthy();
    expect(container.querySelector(".success-check-mark")).toBeTruthy();
  });
});

function Rows({ order }: { order: string[] }) {
  const ref = useRef<HTMLUListElement>(null);
  useFlipList(ref, order.join(","));
  return (
    <ul ref={ref}>
      {order.map((id) => (
        <li key={id} data-flip-key={id}>
          {id}
        </li>
      ))}
    </ul>
  );
}

describe("useFlipList", () => {
  it("slides moved rows from their old position (transform only) and skips the first layout", () => {
    const tops: Record<string, number> = { a: 0, b: 40, c: 80 };
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return { left: 0, top: tops[this.dataset.flipKey ?? ""] ?? 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) };
    });
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as { animate: unknown }).animate = animate;
    const { rerender } = render(<Rows order={["a", "b", "c"]} />);
    expect(animate).not.toHaveBeenCalled();
    tops.a = 80;
    tops.c = 0;
    rerender(<Rows order={["c", "b", "a"]} />);
    expect(animate).toHaveBeenCalledTimes(2);
    const frames = animate.mock.calls.map((call) => call[0][0].transform);
    expect(frames).toContain("translate(0px, -80px)");
    expect(frames).toContain("translate(0px, 80px)");
    expect(animate.mock.calls[0][0][1]).toEqual({ transform: "none" });
  });
  it("does nothing under reduced motion", () => {
    mockMatchMedia(true);
    const tops: Record<string, number> = { a: 0, b: 40 };
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return { left: 0, top: tops[this.dataset.flipKey ?? ""] ?? 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) };
    });
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as { animate: unknown }).animate = animate;
    const { rerender } = render(<Rows order={["a", "b"]} />);
    tops.a = 40;
    tops.b = 0;
    rerender(<Rows order={["b", "a"]} />);
    expect(animate).not.toHaveBeenCalled();
  });
});

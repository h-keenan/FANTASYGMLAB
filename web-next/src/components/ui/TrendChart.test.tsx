import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TrendChart } from "./TrendChart";

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 300, height: 160, top: 0, left: 0, right: 300, bottom: 160, x: 0, y: 0, toJSON: () => ({}) });
});
afterEach(() => vi.restoreAllMocks());

const p = (x: number, y: number | null, gap?: "bye" | "injured" | "missing") => ({ x, y, gap, label: `Wk ${x}` });

describe("TrendChart", () => {
  it("renders a labelled stat for a single played point, never a lone dot", () => {
    render(<TrendChart name="Micah Jennings" unit="pts" points={[p(1, 25.7)]} />);
    const stat = screen.getByTestId("trend-chart-single");
    expect(stat.textContent).toContain("25.7");
    expect(stat.textContent).toContain("Wk 1");
    expect(stat.textContent).toContain("Not enough weeks yet for a trend");
    expect(document.querySelector("svg")).toBeNull();
  });
  it("says so when there is nothing", () => {
    render(<TrendChart name="X" points={[]} />);
    expect(screen.getByText("No weeks recorded yet")).toBeTruthy();
  });
  it("a bye in the middle is a dashed bridge and a muted marker, with a legend", () => {
    render(<TrendChart name="X" unit="pts" points={[p(1, 10), p(2, 14), p(3, null, "bye"), p(4, 20), p(5, 18)]} />);
    expect(screen.getAllByTestId("trend-bridge")).toHaveLength(1);
    expect(screen.getAllByTestId("trend-gap-marker")).toHaveLength(1);
    expect(screen.getByText("Dashed: bye week")).toBeTruthy();
  });
  it("tapping a gap or a point shows its tooltip, tapping again hides it", () => {
    render(<TrendChart name="X" unit="pts" points={[p(1, 10), p(2, null, "bye"), p(3, 20), p(4, 18)]} />);
    fireEvent.click(screen.getByRole("button", { name: "Wk 2 · Bye week" }));
    expect(screen.getByRole("status").textContent).toBe("Wk 2 · Bye week");
    fireEvent.click(screen.getByRole("button", { name: "Wk 2 · Bye week" }));
    expect(screen.queryByRole("status")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Wk 3 · 20.0 pts" }));
    expect(screen.getByRole("status").textContent).toBe("Wk 3 · 20.0 pts");
  });
  it("two or three points print their values on the dots", () => {
    render(<TrendChart name="X" points={[p(1, 10), p(2, 14)]} />);
    expect(screen.getByTestId("trend-chart").getAttribute("data-status")).toBe("sparse");
    expect(screen.getByText("14.0")).toBeTruthy();
  });
  it("compact has no axes or legend", () => {
    render(<TrendChart name="X" variant="compact" points={[p(1, 10), p(2, null), p(3, 20), p(4, 18)]} />);
    expect(document.querySelector("text")).toBeNull();
    expect(screen.queryByText(/Dashed/)).toBeNull();
  });
  it("a projection band keeps one played week on a real chart", () => {
    render(<TrendChart name="X" points={[p(1, 25.7)]} band={[{ x: 2, mean: 20, floor: 12, ceiling: 30 }, { x: 3, mean: 20, floor: 12, ceiling: 30 }]} />);
    expect(screen.getByTestId("trend-chart").getAttribute("data-status")).toBe("ready");
  });
  it("gives the whole chart one accessible sentence", () => {
    render(<TrendChart name="Micah Jennings" unit="pts" points={[p(1, 10), p(2, 14), p(3, 12), p(4, 20)]} />);
    expect(document.querySelector("svg")?.getAttribute("aria-label")).toContain("Micah Jennings: 4 weeks");
  });
});

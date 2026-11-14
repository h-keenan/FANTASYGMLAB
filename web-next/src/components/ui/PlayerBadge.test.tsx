import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BadgeLegendSheet, PlayerBadge, PlayerBadges } from "./PlayerBadge";

describe("PlayerBadge", () => {
  it("draws a glyph, names it for screen readers and keeps the full word out of the visible text", () => {
    render(<PlayerBadge kind="rookie" />);
    const badge = screen.getByRole("img", { name: "Rookie" });
    expect(badge).toHaveAttribute("title", "Rookie");
    expect(badge).toHaveTextContent("R");
    expect(badge).not.toHaveTextContent("Rookie");
  });
  it("shows the detail only when asked (quick view), and always names it", () => {
    const { rerender } = render(<PlayerBadge kind="out" detail="2 wks" />);
    expect(screen.getByRole("img", { name: "Out: 2 wks" })).not.toHaveTextContent("wks");
    rerender(<PlayerBadge kind="out" detail="2 wks" showDetail />);
    expect(screen.getByRole("img", { name: "Out: 2 wks" })).toHaveTextContent("2 wks");
  });
  it("suppresses a kind, caps the strip and folds the rest into +n", () => {
    render(<PlayerBadges badges={[{ kind: "rookie" }, { kind: "ir" }, { kind: "taxi" }, { kind: "fa" }, { kind: "bench" }]} suppress={["rookie"]} max={2} />);
    const strip = screen.getByTestId("player-badges");
    expect(strip.querySelectorAll("[data-badge]")).toHaveLength(2);
    expect(screen.queryByRole("img", { name: "Rookie" })).toBeNull();
    expect(strip).toHaveTextContent("+2");
    expect(strip).toHaveAttribute("aria-label", expect.stringContaining("plus 2 more"));
  });
  it("renders nothing when every badge is suppressed", () => {
    const { container } = render(<PlayerBadges badges={[{ kind: "rookie" }]} suppress={["rookie"]} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("opens the legend from the strip when it is a tap target", () => {
    let opened = 0;
    render(<PlayerBadges badges={[{ kind: "questionable" }]} onLegend={() => (opened += 1)} />);
    fireEvent.click(screen.getByRole("button", { name: /What the symbols mean/ }));
    expect(opened).toBe(1);
  });
  it("the legend sheet explains every symbol", () => {
    render(<BadgeLegendSheet open onClose={() => {}} />);
    expect(screen.getByTestId("badge-legend").querySelectorAll("[data-testid=legend-badge]").length).toBeGreaterThanOrEqual(15);
    expect(screen.getByText("Rookie: first NFL season.")).toBeInTheDocument();
  });
});

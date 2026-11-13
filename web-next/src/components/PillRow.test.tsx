import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PillRow } from "./PillRow";

const OPTIONS = [
  { label: "All", value: "all" },
  { label: "Trades", value: "trades" },
  { label: "Waivers / Free Agents", value: "waivers" },
];

describe("PillRow", () => {
  it("is a tablist of tabs with aria-selected and roving tabindex", () => {
    render(<PillRow options={OPTIONS} active="trades" onSelect={() => {}} ariaLabel="Filter" />);
    expect(screen.getByRole("tablist", { name: "Filter" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Trades" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "All" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: "Trades" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "All" })).toHaveAttribute("tabindex", "-1");
  });

  it("moves focus and selection with arrow keys, wrapping, plus Home/End", () => {
    const onSelect = vi.fn();
    render(<PillRow options={OPTIONS} active="all" onSelect={onSelect} />);
    const all = screen.getByRole("tab", { name: "All" });
    all.focus();
    fireEvent.keyDown(all, { key: "ArrowRight" });
    expect(onSelect).toHaveBeenLastCalledWith("trades");
    expect(screen.getByRole("tab", { name: "Trades" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Trades" }), { key: "End" });
    expect(onSelect).toHaveBeenLastCalledWith("waivers");
    fireEvent.keyDown(screen.getByRole("tab", { name: "Waivers / Free Agents" }), { key: "ArrowRight" });
    expect(onSelect).toHaveBeenLastCalledWith("all");
  });

  it("never wraps: segments are single-line in every variant", () => {
    for (const variant of ["fill", "compact", "scroll"] as const) {
      const { unmount } = render(<PillRow options={OPTIONS} active="all" variant={variant} />);
      for (const tab of screen.getAllByRole("tab")) expect(tab.className).toContain("whitespace-nowrap");
      expect(screen.getByRole("tablist").className).toContain("overflow-x-auto");
      unmount();
    }
  });

  it("hugs content in compact and spans the row in fill", () => {
    const { container, rerender } = render(<PillRow options={OPTIONS} active="all" variant="compact" />);
    expect((container.firstChild as HTMLElement).className).toContain("self-start");
    rerender(<PillRow options={OPTIONS} active="all" fullWidth />);
    expect((container.firstChild as HTMLElement).className).toContain("w-full");
  });

  it("renders registry glyphs as decorative SVGs and keeps the accessible name the label", () => {
    const options = [
      { label: "Home", value: "home", glyph: "home" as const },
      { label: "Team", value: "team", glyph: "team" as const },
      { label: "Players", value: "players", glyph: "players" as const },
      { label: "Trades", value: "trades", glyph: "trades" as const, count: 2 },
      { label: "League", value: "league", glyph: "league" as const },
      { label: "More", value: "more", glyph: "more" as const },
    ];
    render(<PillRow options={options} active="home" variant="fill" ariaLabel="Game sections" />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(6);
    for (const tab of tabs) {
      expect(tab.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
      // Six icon tabs split the width equally so the last one is never clipped on a phone.
      expect(tab.className).toContain("min-w-0");
      expect(tab.style.minHeight).toBe("var(--segmented-height)");
    }
    expect(screen.getByLabelText("2 new")).toBeInTheDocument();
  });

  it("uses the full touch target on sticky bars that carry icons", () => {
    render(<PillRow sticky fullWidth options={[{ label: "Hub", value: "hub", glyph: "hub" }, { label: "Finder", value: "finder", glyph: "finder" }]} active="hub" />);
    expect(screen.getAllByRole("tab")[0].style.minHeight).toBe("var(--segmented-height)");
  });
});

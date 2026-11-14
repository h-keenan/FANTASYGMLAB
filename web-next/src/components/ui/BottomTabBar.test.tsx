import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { simGameBottomTabs } from "@/lib/bottomNav";

import { BottomTabBar } from "./BottomTabBar";

describe("BottomTabBar", () => {
  it("is a labelled nav with the active tab marked aria-current", () => {
    render(<BottomTabBar ariaLabel="Game sections" tabs={simGameBottomTabs({ inbox: 2 })} active="team" />);
    const nav = screen.getByRole("navigation", { name: "Game sections" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Team" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("shows the badge count and reads it in the name", () => {
    render(<BottomTabBar ariaLabel="Game sections" tabs={simGameBottomTabs({ inbox: 12 })} active="home" />);
    expect(screen.getByTestId("bottom-tab-badge-trades")).toHaveTextContent("9+");
    expect(screen.getByRole("button", { name: "Trades, 12 new" })).toBeInTheDocument();
    expect(screen.queryByTestId("bottom-tab-badge-team")).toBeNull();
  });

  it("selects a tab on tap and falls back to the first tab for an unknown key", () => {
    const onSelect = vi.fn();
    render(<BottomTabBar ariaLabel="Game sections" tabs={simGameBottomTabs({})} active="more" onSelect={onSelect} />);
    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "League" }));
    expect(onSelect).toHaveBeenCalledWith("league");
  });

  it("renders link tabs when a tab has an href", () => {
    render(<BottomTabBar ariaLabel="Site" tabs={[{ key: "today", label: "Today", glyph: "home", href: "/dashboard/1" }]} active="today" />);
    expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/dashboard/1");
  });
});

describe("BottomTabBar look", () => {
  it("gives every tab, the More button included, the same icon slot and label markup", () => {
    const tabs = [
      { key: "a", label: "Today", glyph: "home" as const, href: "/a" },
      { key: "more", label: "More", glyph: "more" as const },
    ];
    const { container } = render(<BottomTabBar ariaLabel="x" tabs={tabs} active="a" />);
    const items = container.querySelectorAll(".bottom-tab");
    expect(items).toHaveLength(2);
    items.forEach((el) => {
      expect(el.querySelectorAll(".bottom-tab-icon svg")).toHaveLength(1);
      expect(el.querySelectorAll(".bottom-tab-label")).toHaveLength(1);
    });
    expect(items[0].tagName).toBe("A");
    expect(items[1].tagName).toBe("BUTTON");
    expect(items[0]).toHaveAttribute("aria-current", "page");
    expect(items[1]).not.toHaveAttribute("aria-current");
  });
});

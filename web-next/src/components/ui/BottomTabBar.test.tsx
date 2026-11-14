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

describe("BottomTabBar smart pill (page context)", () => {
  const ctx = (over: Partial<import("@/lib/bottomNav").PillContext> = {}): import("@/lib/bottomNav").PillContext => ({
    id: "team",
    label: "Team sections",
    tabs: [
      { key: "lineup", label: "Lineup" },
      { key: "players", label: "Players" },
      { key: "waivers", label: "Waivers" },
    ],
    activeKey: "lineup",
    onSelect: () => {},
    primary: { key: "auto", label: "Auto-set", onPress: () => {} },
    ...over,
  });
  const tabs = [
    { key: "today", label: "Today", glyph: "home" as const, href: "/d" },
    { key: "team", label: "Team", glyph: "team" as const, href: "/t" },
    { key: "more", label: "More", glyph: "more" as const },
  ];

  it("without context there is no page layer and mode is global", () => {
    render(<BottomTabBar ariaLabel="x" tabs={tabs} active="team" />);
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "global");
    expect(screen.queryByTestId("pill-context-layer")).toBeNull();
  });

  it("with context: section icon, menu button, a page tablist and one primary", () => {
    const onSelect = vi.fn();
    const onPress = vi.fn();
    render(<BottomTabBar ariaLabel="x" tabs={tabs} active="team" context={ctx({ onSelect, primary: { key: "auto", label: "Auto-set", onPress } })} />);
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "context");
    expect(screen.getByRole("tablist", { name: "Team sections" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Lineup" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Players" })).toHaveAttribute("aria-selected", "false");
    fireEvent.click(screen.getByRole("tab", { name: "Players" }));
    expect(onSelect).toHaveBeenCalledWith("players");
    fireEvent.click(screen.getByTestId("pill-primary"));
    expect(onPress).toHaveBeenCalled();
    expect(screen.getByTestId("pill-section")).toHaveAttribute("aria-label", "Team");
  });

  it("the menu button toggles aria-expanded and the full global row; picking a tab folds it back", () => {
    const onSelect = vi.fn();
    render(<BottomTabBar ariaLabel="x" tabs={tabs} active="team" onSelect={onSelect} context={ctx()} />);
    const menu = screen.getByTestId("pill-menu");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(menu);
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "menu");
    expect(menu).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("link", { name: "Today" }));
    expect(onSelect).toHaveBeenCalledWith("today");
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "context");
  });

  it("Escape folds the menu", () => {
    render(<BottomTabBar ariaLabel="x" tabs={tabs} active="team" context={ctx()} />);
    fireEvent.click(screen.getByTestId("pill-menu"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "context");
  });

  it("a context with nothing to show renders the plain global pill", () => {
    render(<BottomTabBar ariaLabel="x" tabs={tabs} active="team" context={ctx({ tabs: [], primary: undefined })} />);
    expect(screen.getByTestId("bottom-tab-bar")).toHaveAttribute("data-mode", "global");
  });

  it("route tabs and a route primary render as links (client navigation)", () => {
    render(
      <BottomTabBar
        ariaLabel="x"
        tabs={tabs}
        active="team"
        context={ctx({ tabs: [{ key: "hub", label: "Hub", href: "/trade-hub/1" }, { key: "finder", label: "Finder", href: "/trade-finder/1" }], activeKey: "hub", primary: { key: "new", label: "New trade", href: "/trade-analyzer/1", onPress: () => {} } })}
      />,
    );
    expect(screen.getByRole("tab", { name: "Finder" })).toHaveAttribute("href", "/trade-finder/1");
    expect(screen.getByTestId("pill-primary")).toHaveAttribute("href", "/trade-analyzer/1");
  });
});

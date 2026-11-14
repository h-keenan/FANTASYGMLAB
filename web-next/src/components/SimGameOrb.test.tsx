import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimGameOrb } from "./SimGameOrb";

const base = { tab: "home" as const, offseason: false, inbox: 0, onTab: vi.fn(), onMore: vi.fn(), onHub: vi.fn() };

describe("SimGameOrb", () => {
  it("names the current page and shows the trade-offer badge", () => {
    render(<SimGameOrb {...base} tab="team" inbox={2} />);
    expect(screen.getByRole("button", { name: "Team 2. Game menu, 2 trade offers waiting" })).toBeInTheDocument();
    expect(screen.getByTestId("sim-game-orb-badge")).toHaveTextContent("2");
  });

  it("has no badge when nothing is pending", () => {
    render(<SimGameOrb {...base} />);
    expect(screen.queryByTestId("sim-game-orb-badge")).toBeNull();
  });

  it("opens the navigator in one tap, lights the current page and goes in one more", () => {
    const onTab = vi.fn();
    render(<SimGameOrb {...base} tab="league" inbox={1} onTab={onTab} />);
    fireEvent.click(screen.getByTestId("sim-game-orb"));
    const nav = screen.getByRole("navigation", { name: "Game pages" });
    expect(nav).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /^League/ })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("button", { name: /^Home/ })).not.toHaveAttribute("aria-current");
    fireEvent.click(within(nav).getByRole("button", { name: /^Trades/ }));
    expect(onTab).toHaveBeenCalledWith("trades");
  });

  it("offers More, All games, search and a way home", () => {
    const onMore = vi.fn();
    const onHub = vi.fn();
    render(<SimGameOrb {...base} onMore={onMore} onHub={onHub} />);
    fireEvent.click(screen.getByTestId("sim-game-orb"));
    expect(screen.getByRole("link", { name: /Back to FantasyDesk home/ })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: /Search players and pages/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /All games/ }));
    expect(onHub).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("sim-game-orb"));
    fireEvent.click(screen.getByRole("button", { name: /More.*Rules/ }));
    expect(onMore).toHaveBeenCalled();
  });

  it("styles the menu rows like the FantasyDesk More sheet: tinted glyph, label over a subtitle", () => {
    render(<SimGameOrb {...base} />);
    fireEvent.click(screen.getByTestId("sim-game-orb"));
    const nav = screen.getByTestId("sim-game-nav");
    expect(nav).toHaveTextContent("Lineup, bench, and roster moves");
    expect(nav.querySelectorAll(".game-nav-row span.shrink-0").length).toBeGreaterThanOrEqual(6);
  });

  it("drops Players in the offseason", () => {
    render(<SimGameOrb {...base} offseason />);
    fireEvent.click(screen.getByTestId("sim-game-orb"));
    const nav = screen.getByRole("navigation", { name: "Game pages" });
    expect(within(nav).queryByRole("button", { name: /^Players/ })).toBeNull();
    expect(within(nav).getByRole("button", { name: /^Offseason/ })).toBeInTheDocument();
  });
});

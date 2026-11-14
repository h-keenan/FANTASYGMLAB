import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageTabBar } from "./PageTabBar";

describe("PageTabBar", () => {
  it("renders the Team family as route tabs with the active one selected", () => {
    render(<PageTabBar family="team" active="waivers" leagueId="9" leagueName="My League" />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Roster", "Players", "Waivers", "Matchup"]);
    expect(screen.getByRole("tab", { name: "Waivers" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Roster" })).toHaveAttribute("href", "/my-team/9?name=My%20League");
    expect(screen.getByRole("tablist")).toHaveAttribute("aria-label", "Team section");
  });
  it("renders the League family on the glass strip", () => {
    const { container } = render(<PageTabBar family="league" active="games" leagueId="9" leagueName="L" />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Rankings", "Recaps", "Games"]);
    expect(container.querySelector(".pill-row-glass")).not.toBeNull();
    expect(screen.getByRole("tab", { name: "Recaps" })).toHaveAttribute("href", "/league-recaps/9?name=L");
  });
  it("keeps Trade History account-wide with the league as a query", () => {
    render(<PageTabBar family="trades" active="trade_history" leagueId="9" leagueName="L" />);
    expect(screen.getByRole("tab", { name: "History" })).toHaveAttribute("href", "/trade-history?league=9&name=L");
  });
});

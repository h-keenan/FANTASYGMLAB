import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ThisWeekStrip } from "./ThisWeekStrip";
import { thisWeekHref } from "@/lib/thisWeek";
import type { ThisWeek } from "@/lib/api";

const IN_SEASON: ThisWeek = {
  mode: "in_season",
  week: 7,
  next_action: null,
  rows: [
    {
      key: "lineup",
      status: "Check",
      tone: "risk",
      headline: "Check Matchup: Starter RB is out",
      why: "A starter who can't play scores zero. You have a healthy RB on your bench who can step in.",
      cta_label: "Review lineup",
      route: "matchup",
      player_id: "2",
    },
    {
      key: "waiver",
      status: "Add",
      tone: "waiver",
      headline: "Top add: Free Agent",
      why: "Fills your RB2 hole.",
      cta_label: "Claim a waiver",
      route: "waivers",
      player_id: "99",
    },
    {
      key: "trade",
      status: "Hold",
      tone: "neutral",
      headline: "Hold: no trade improves your team",
      why: "No offer in your league clears the value bar right now.",
      cta_label: null,
      route: null,
      player_id: "",
    },
  ],
};

describe("ThisWeekStrip", () => {
  it("renders the three moves with action-phrased buttons and links", () => {
    render(<ThisWeekStrip data={IN_SEASON} leagueId="abc" leagueName="My League" />);
    expect(screen.getByRole("heading", { name: "This week · Week 7" })).toBeInTheDocument();
    expect(screen.getByText("Check Matchup: Starter RB is out")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review lineup" })).toHaveAttribute("href", "/matchup/abc?name=My+League");
    expect(screen.getByRole("link", { name: "Claim a waiver" })).toHaveAttribute(
      "href",
      "/waivers/abc?name=My+League&playerId=99",
    );
    // Hold is a verdict, not an action: no button.
    expect(screen.getByText("Hold: no trade improves your team")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("shows one next action outside the season and never an empty card", () => {
    const data: ThisWeek = {
      mode: "next_action",
      week: null,
      rows: [],
      next_action: { headline: "Connect a league to get started", why: "Link Sleeper.", cta_label: "Connect a league", route: "connect_league" },
    };
    render(<ThisWeekStrip data={data} leagueId="abc" leagueName="L" />);
    expect(screen.getByRole("link", { name: "Connect a league" })).toHaveAttribute("href", "/connect-league");
  });

  it("renders nothing when there are no rows and no next action", () => {
    const { container } = render(
      <ThisWeekStrip data={{ mode: "in_season", week: 3, rows: [], next_action: null }} leagueId="a" leagueName="L" />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("builds draft routes", () => {
    expect(thisWeekHref("draft_center", "x y", "L")).toBe("/draft-center/x%20y?name=L");
  });

  it("reserves the trade row's space on the deferred first pass and drops it once the row arrives", () => {
    const withoutTrade: ThisWeek = { ...IN_SEASON, rows: IN_SEASON.rows.filter((row) => row.key !== "trade") };
    const { container, rerender } = render(<ThisWeekStrip data={withoutTrade} leagueId="a" leagueName="L" tradePending />);
    expect(container.querySelector("[data-fgl-this-week-trade-pending]")).not.toBeNull();
    expect(screen.queryByText(/Hold: no trade improves/)).toBeNull();
    rerender(<ThisWeekStrip data={IN_SEASON} leagueId="a" leagueName="L" />);
    expect(container.querySelector("[data-fgl-this-week-trade-pending]")).toBeNull();
  });
});

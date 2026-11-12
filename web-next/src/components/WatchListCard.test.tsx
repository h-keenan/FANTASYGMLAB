import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WatchListCard } from "./WatchListCard";
import type { BriefingItem } from "@/lib/api";

function item(overrides: Partial<BriefingItem>): BriefingItem {
  return {
    category: "waiver_opportunity",
    headline: "Add Jaylen Warren",
    reason: "Your RB2 is banged up and Warren is the clear best fit on the wire.",
    supporting_context: null,
    destination: "waivers",
    route_player_id: "",
    route_player_name: "",
    route_player_position: "",
    route_player_team: "",
    route_player_tier: "",
    route_player_score: null,
    route_player_injury_status: "",
    mentioned_players: [],
    recommendation_narrative: null,
    presentation: null,
    recommendation_id: "rec-1",
    tier_label: "",
    ...overrides,
  };
}

describe("WatchListCard", () => {
  // Recommendation-compliance audit, Check 3 — CTA reachability: this card
  // renders Waiver Opportunity/Watch/League Movement items (every non-Top-
  // Priority Game Plan item), so its own "Open Waivers" CTA used to link to
  // the generic `/waivers/{leagueId}` with no way to tell which free agent
  // the tile named — same bug as GamePlanCard, fixed the same way.
  it("encodes the item's route_player_id into the waivers CTA link", () => {
    render(
      <WatchListCard
        items={[item({ route_player_id: "4046", route_player_name: "Jaylen Warren" })]}
        leagueId="abc"
        leagueName="Revivalry"
      />,
    );

    const link = screen.getByRole("link", { name: /Open Waivers/ });
    expect(link).toHaveAttribute("href", "/waivers/abc?name=Revivalry&playerId=4046");
  });

  it("omits playerId from the CTA link when the item has no route player", () => {
    render(<WatchListCard items={[item({ route_player_id: "" })]} leagueId="abc" leagueName="Revivalry" />);

    const link = screen.getByRole("link", { name: /Open Waivers/ });
    expect(link).toHaveAttribute("href", "/waivers/abc?name=Revivalry");
  });

  // Recommendation-compliance audit, Check 3 follow-up — My Team's own
  // injury-alert/value-trend tiles (destination "my_team") carry
  // route_player_id the same way waiver tiles do (modules/dashboard_engine's
  // build_injury_tile/build_value_trend_tile), and gamePlanTileHref already
  // builds that destination's href the same generic way — this just locks
  // in that the CTA link itself already carries ?playerId= for my_team,
  // same as it does for waivers.
  it("encodes the item's route_player_id into the My Team CTA link", () => {
    render(
      <WatchListCard
        items={[
          item({
            destination: "my_team",
            headline: "Monitor Jaylen Warren's usage",
            route_player_id: "4046",
            route_player_name: "Jaylen Warren",
          }),
        ]}
        leagueId="abc"
        leagueName="Revivalry"
      />,
    );

    const link = screen.getByRole("link", { name: /Open My Team/ });
    expect(link).toHaveAttribute("href", "/my-team/abc?name=Revivalry&playerId=4046");
  });

  it("renders nothing for an empty item list", () => {
    const { container } = render(<WatchListCard items={[]} leagueId="abc" leagueName="Revivalry" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("WatchListCard bye cover alert", () => {
  const bye = item({
    category: "watch",
    headline: "Your WR1 (Wade WR) is on bye in Week 9",
    reason: "Look at the waiver wire for a fill-in: Fits One, Fits Two. You have no other healthy WR to start.",
    supporting_context: "Bye Week Cover",
    route_player_id: "3",
    route_player_name: "Wade WR",
    route_player_position: "WR",
    route_player_team: "AAA",
    mentioned_players: [
      { player_id: "10", name: "Fits One", position: "WR", team: "BBB", player_tier: "", injury_status: "" },
      { player_id: "13", name: "Fits Two", position: "WR", team: "CCC", player_tier: "", injury_status: "" },
    ],
    presentation: { bye_cover: { week: 9, slot_label: "WR1" } },
    recommendation_id: "bye-1",
  });

  it("tags the week, names the bye player and lists fill-ins with photos", () => {
    render(<WatchListCard items={[bye]} leagueId="abc" leagueName="Revivalry" />);
    expect(screen.getByText("Bye Wk 9")).toBeInTheDocument();
    expect(screen.getByText("Wade WR")).toBeInTheDocument();
    expect(screen.getByText(/WR1 on bye in Week 9\. Look at the waiver wire for a fill-in: Fits One, Fits Two\./)).toBeInTheDocument();
    const strip = screen.getByTestId("bye-cover-fillins");
    expect(strip).toHaveTextContent("Fits One");
    expect(strip).toHaveTextContent("Fits Two");
  });

  it("links the waivers CTA to the best fill-in, not the rostered starter", () => {
    render(<WatchListCard items={[bye]} leagueId="abc" leagueName="Revivalry" />);
    expect(screen.getByRole("link", { name: /Open Waivers/ })).toHaveAttribute("href", "/waivers/abc?name=Revivalry&playerId=10");
  });
});

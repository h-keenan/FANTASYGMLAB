import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GamePlanCard } from "./GamePlanCard";
import type { BriefingItem } from "@/lib/api";

const BASE: BriefingItem = {
  category: "top_priority",
  headline: "Tony Pollard",
  reason: "You move from TE surplus. Epstein's List moves from RB surplus and gets TE help.",
  supporting_context: null,
  destination: "trade_hub",
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
};

describe("GamePlanCard", () => {
  // coridian_, 2026-10-18: "Top priority still has no player card" — a Top
  // Trade Opportunity tile often has no single route_player_id (it's a
  // 2-sided trade), but modules.dashboard_engine.build_trade_tile always
  // carries the real give/get package under presentation.trade_package.
  it("renders a real give/get player card from presentation.trade_package when route_player_id is empty", () => {
    const item: BriefingItem = {
      ...BASE,
      presentation: {
        trade_package: {
          send: [{ asset_type: "player", player_id: "1", name: "Cade Otton", position: "TE", team: "TB", score: 4165 }],
          receive: [{ asset_type: "player", player_id: "2", name: "Tony Pollard", position: "RB", team: "TEN", score: 4356 }],
          value_edge: "Even",
          confidence: "Medium",
        },
      },
    };
    render(<GamePlanCard item={item} leagueId="abc" leagueName="Revivalry" />);

    expect(screen.getByText("You send")).toBeInTheDocument();
    expect(screen.getByText("You get")).toBeInTheDocument();
    expect(screen.getByText("Cade Otton")).toBeInTheDocument();
    // "Tony Pollard" appears twice — once as the card's own headline, once
    // as the "You get" package's player name.
    expect(screen.getAllByText("Tony Pollard").length).toBeGreaterThanOrEqual(2);
  });

  it("falls back to the single route_player_* avatar row when there is no trade package", () => {
    const item: BriefingItem = {
      ...BASE,
      route_player_id: "4046",
      route_player_name: "Jaylen Warren",
      route_player_team: "PIT",
    };
    render(<GamePlanCard item={item} leagueId="abc" leagueName="Revivalry" />);

    expect(screen.getByText("Jaylen Warren")).toBeInTheDocument();
    expect(screen.queryByText("You send")).not.toBeInTheDocument();
  });

  // coridian_, 2026-10-18, screenshot: "it says watch injured starters and
  // it lists starters but it only shows one player's compact player card" —
  // a "1 injured starter" Watch item routes to the one unambiguous starter
  // (route_player_*) AND names other future-asset players in its reason
  // text (mentioned_players) — both must render, not just whichever one an
  // if/else-if happened to hit first.
  it("shows the route player's card AND every other mentioned player, not just one", () => {
    const item: BriefingItem = {
      ...BASE,
      category: "watch",
      route_player_id: "1",
      route_player_name: "Aaron Jones",
      route_player_team: "MIN",
      mentioned_players: [
        { player_id: "2", name: "Colbie Young", position: "WR", team: "CIN", player_tier: "" },
        { player_id: "1", name: "Aaron Jones", position: "RB", team: "MIN", player_tier: "" },
        { player_id: "3", name: "Jalen Milroe", position: "QB", team: "SEA", player_tier: "" },
      ],
    };
    render(<GamePlanCard item={item} leagueId="abc" leagueName="Revivalry" />);

    expect(screen.getByText("Aaron Jones")).toBeInTheDocument();
    expect(screen.getByText("Colbie Young")).toBeInTheDocument();
    expect(screen.getByText("Jalen Milroe")).toBeInTheDocument();
    // Aaron Jones is both the route player AND in mentioned_players — must
    // render exactly once, not twice.
    expect(screen.getAllByText("Aaron Jones")).toHaveLength(1);
  });

  // Recommendation-compliance audit, Check 3 — CTA reachability: the CTA
  // used to link to a generic `/waivers/{leagueId}` with no way to tell
  // which free agent this tile was about. It must now carry the tile's own
  // route_player_id as a query param so Waivers can land directly on it.
  it("encodes the tile's route_player_id into the waivers CTA link", () => {
    const item: BriefingItem = {
      ...BASE,
      category: "waiver_opportunity",
      destination: "waivers",
      route_player_id: "4046",
      route_player_name: "Jaylen Warren",
    };
    render(<GamePlanCard item={item} leagueId="abc" leagueName="Revivalry" />);

    const link = screen.getByRole("link", { name: /Open Waivers/ });
    expect(link).toHaveAttribute("href", "/waivers/abc?name=Revivalry&playerId=4046");
  });

  it("falls back to the trade package's headline receive player for the trade_hub CTA when route_player_id is empty", () => {
    const item: BriefingItem = {
      ...BASE,
      destination: "trade_hub",
      route_player_id: "",
      presentation: {
        trade_package: {
          send: [{ asset_type: "player", player_id: "1", name: "Cade Otton", position: "TE", team: "TB", score: 4165 }],
          receive: [{ asset_type: "player", player_id: "2", name: "Tony Pollard", position: "RB", team: "TEN", score: 4356 }],
          value_edge: "Even",
          confidence: "Medium",
        },
      },
    };
    render(<GamePlanCard item={item} leagueId="abc" leagueName="Revivalry" />);

    const link = screen.getByRole("link", { name: /Review in Trade Hub/ });
    expect(link).toHaveAttribute("href", "/trade-hub/abc?name=Revivalry&playerId=2");
  });

  it("omits playerId from the CTA link when no route player can be resolved", () => {
    render(<GamePlanCard item={BASE} leagueId="abc" leagueName="Revivalry" />);

    const link = screen.getByRole("link", { name: /Review in Trade Hub/ });
    expect(link).toHaveAttribute("href", "/trade-hub/abc?name=Revivalry");
  });
});

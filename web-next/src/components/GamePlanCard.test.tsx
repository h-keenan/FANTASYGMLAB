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
});

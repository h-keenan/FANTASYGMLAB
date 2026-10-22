import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MatchupContent } from "./MatchupContent";
import type {
  MatchupComparison,
  MatchupRealComparison,
  MatchupRealStarter,
  MatchupResponse,
  MatchupSide,
  MatchupStarter,
} from "@/lib/api";

function starter(overrides: Partial<MatchupStarter>): MatchupStarter {
  return {
    player_id: "p1",
    name: "Test Starter",
    position: "RB",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 1500,
    slot: "RB",
    suggested_starter: true,
    roster_slot: "starter",
    opportunity_label: "Lead back",
    overall_rating: 82,
    why: "Elite tier · Lead back · top RB on this roster by season value",
    projection: { status: "ok", point_estimate: 13.1, low: 9.4, high: 16.8, confidence: "medium", opponent: "SEA" },
    ...overrides,
  };
}

function realStarter(overrides: Partial<MatchupRealStarter>): MatchupRealStarter {
  return {
    player_id: "p1",
    name: "Test Starter",
    position: "RB",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    injury_label: "",
    tier: "starter",
    score: 1500,
    opportunity_label: "Lead back",
    overall_rating: 82,
    actual_points: 14.2,
    projection: { status: "ok", point_estimate: 13.1, low: 9.4, high: 16.8, confidence: "medium", opponent: "SEA" },
    game_started: true,
    ...overrides,
  };
}

function side(overrides: Partial<MatchupSide>): MatchupSide {
  return {
    roster_id: "1",
    team_name: "Dynasty Overlords",
    owner_name: "coridian_",
    avatar_url: null,
    wins: 5,
    losses: 2,
    ties: 0,
    starters: [starter({})],
    season_value_total: 8200,
    starters_basis: "suggested_optimal_lineup",
    real_starters: [],
    real_points: null,
    has_live_data: false,
    real_starters_basis: "sleeper_actual_lineup",
    ...overrides,
  };
}

const COMPARISON: MatchupComparison = {
  my_season_value: 8200,
  opponent_season_value: 7600,
  margin: 600,
  edge: "you",
  headline: "Your lineup carries the stronger season-long value",
  basis: "season_value",
  basis_label: "Season-long value & opportunity signal — not a weekly points projection.",
};

const BASE_RESPONSE: MatchupResponse = {
  ok: true,
  week: 7,
  my_team: side({ team_name: "Dynasty Overlords" }),
  opponent: side({ roster_id: "2", team_name: "Rival Squad", season_value_total: 7600 }),
  comparison: COMPARISON,
  real_comparison: null,
  win_probability: null,
  basis: "season_value",
  basis_label: COMPARISON.basis_label,
  reason: "",
};

describe("MatchupContent", () => {
  it("renders the league name, week badge, and season-value verdict", () => {
    render(<MatchupContent leagueName="My League" matchup={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "My League" })).toBeInTheDocument();
    expect(screen.getByText("WEEK 7")).toBeInTheDocument();
    expect(screen.getByText(/Your lineup carries the stronger season-long value/)).toBeInTheDocument();
    expect(screen.getAllByText("Dynasty Overlords").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rival Squad").length).toBeGreaterThan(0);
  });

  it("shows the LIVE badge and real-points verdict once both sides have live data", () => {
    const realComparison: MatchupRealComparison = {
      my_points: 42.3,
      opponent_points: 38.1,
      margin: 4.2,
      edge: "you",
      basis: "sleeper_actual_lineup",
      basis_label: "Your actual current-week lineup and live points, straight from Sleeper.",
    };
    const live: MatchupResponse = {
      ...BASE_RESPONSE,
      real_comparison: realComparison,
      my_team: side({
        team_name: "Dynasty Overlords",
        has_live_data: true,
        real_starters: [realStarter({})],
        real_points: 42.3,
      }),
      opponent: side({
        roster_id: "2",
        team_name: "Rival Squad",
        has_live_data: true,
        real_starters: [realStarter({ player_id: "p2", name: "Opponent Starter" })],
        real_points: 38.1,
      }),
    };

    render(<MatchupContent leagueName="My League" matchup={live} />);

    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText(/You're ahead on live points/)).toBeInTheDocument();
    expect(screen.getByText("Your actual lineup this week")).toBeInTheDocument();
    expect(screen.getByText("Rival Squad's actual lineup")).toBeInTheDocument();
    expect(screen.getAllByText("14.2").length).toBeGreaterThan(0);
  });

  it("leads with the projection, not a misleading 0.0, before a real starter's game has started", () => {
    const notStarted: MatchupResponse = {
      ...BASE_RESPONSE,
      real_comparison: null,
      my_team: side({
        has_live_data: true,
        real_starters: [
          realStarter({
            actual_points: 0,
            game_started: false,
            projection: { status: "ok", point_estimate: 11.5, low: 8, high: 15, confidence: "high", opponent: "SEA" },
          }),
        ],
      }),
    };

    render(<MatchupContent leagueName="My League" matchup={notStarted} />);

    expect(screen.getByText("Proj 11.5")).toBeInTheDocument();
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });

  it("shows the suggested-lineup disclosure and each side's best lineup", () => {
    render(<MatchupContent leagueName="My League" matchup={BASE_RESPONSE} />);

    fireEvent.click(screen.getByRole("button", { name: /Suggested starters, not set lineups/ }));
    expect(screen.getByText(/each roster's best available lineup by season-long value/)).toBeInTheDocument();
    expect(screen.getByText("Your suggested starters")).toBeInTheDocument();
    expect(screen.getByText("Rival Squad's best lineup")).toBeInTheDocument();
    expect(screen.getByText("8,200 SEASON VALUE")).toBeInTheDocument();
  });

  it("shows the matchup-specific not-ready message instead of the board when `reason` is set", () => {
    const byeWeek: MatchupResponse = {
      ...BASE_RESPONSE,
      my_team: null,
      opponent: null,
      comparison: null,
      reason: "bye_week",
    };
    render(<MatchupContent leagueName="My League" matchup={byeWeek} />);

    expect(screen.getByText(/enjoy the bye/)).toBeInTheDocument();
  });

  it("uses Matchup's own copy for not_a_member_of_league instead of the shared link-account copy", () => {
    const notMember: MatchupResponse = {
      ...BASE_RESPONSE,
      my_team: null,
      opponent: null,
      comparison: null,
      reason: "not_a_member_of_league",
    };
    render(<MatchupContent leagueName="My League" matchup={notMember} />);

    expect(screen.getByText("You don't appear to own a team in this league.")).toBeInTheDocument();
  });

  it("shows each suggested-lineup starter's own per-game projection, not just season value", () => {
    render(<MatchupContent leagueName="My League" matchup={BASE_RESPONSE} />);

    // The default `starter()` fixture carries a point_estimate of 13.1.
    expect(screen.getAllByText(/Proj 13\.1/).length).toBeGreaterThan(0);
  });

  it("shows real win odds (not the value lean) once win_probability is available", () => {
    const withOdds: MatchupResponse = {
      ...BASE_RESPONSE,
      win_probability: {
        available: true,
        probability: 0.73,
        my_projected_total: 112.4,
        opponent_projected_total: 96.1,
        coverage: { my: 1, opponent: 1 },
      },
    };

    render(<MatchupContent leagueName="My League" matchup={withOdds} />);

    expect(screen.getByText(/Win odds: you 73% · opponent 27%/)).toBeInTheDocument();
  });

  it("fills the win-probability bar to the real percentage, not capped at half", () => {
    // coridian_, 2026-10-18 (screenshot, near-0%/100% matchup): "why does
    // that bar only take up half then?" — the old shared .lean-bar-* track
    // was a deviation-from-even indicator capped at 50% width by design
    // (correct for Trade Hub's imbalance concept, wrong for an absolute
    // probability). A real win-probability split must fill the track by
    // its own percentage, full range.
    const blowout: MatchupResponse = {
      ...BASE_RESPONSE,
      win_probability: {
        available: true,
        probability: 0.02,
        my_projected_total: 60,
        opponent_projected_total: 140,
        coverage: { my: 1, opponent: 1 },
      },
    };

    const { container } = render(<MatchupContent leagueName="My League" matchup={blowout} />);

    const fill = container.querySelector(".winprob-bar-fill");
    expect(fill).toHaveStyle({ width: "2%" });
    expect(container.querySelector(".lean-bar-track")).not.toBeInTheDocument();
  });

  it("falls back to the value lean (no percentage) when win_probability is unavailable", () => {
    const noOdds: MatchupResponse = {
      ...BASE_RESPONSE,
      win_probability: { available: false, reason: "insufficient_coverage", coverage: { my: 0.2, opponent: 1 } },
    };

    render(<MatchupContent leagueName="My League" matchup={noOdds} />);

    expect(screen.queryByText(/Win odds:/)).not.toBeInTheDocument();
  });
});

describe("MatchupContent best ball", () => {
  it("hides the suggested lineups and start/sit disclosure in a best ball league", () => {
    render(
      <MatchupContent
        leagueName="My League"
        matchup={{ ...BASE_RESPONSE, best_ball: true, lineup_advice_message: "Best ball league: no start/sit." }}
      />,
    );
    expect(screen.getByText("Best ball league: no start/sit.")).toBeInTheDocument();
    expect(screen.queryByText("Your suggested starters")).not.toBeInTheDocument();
    expect(screen.queryByText(/each roster's best available lineup by season-long value/)).not.toBeInTheDocument();
  });
});

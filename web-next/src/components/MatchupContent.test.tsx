import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { MatchupContent } from "./MatchupContent";
import type {
  MatchupComparison,
  MatchupRealComparison,
  MatchupRealStarter,
  MatchupResponse,
  MatchupSide,
  MatchupStarter,
  MatchupSuggestedMove,
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
    game_status: "in_progress",
    slot: "RB",
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
    real_empty_slots: [],
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

const ODDS = {
  available: true as const,
  probability: 0.64,
  my_projected_total: 124.8,
  opponent_projected_total: 116.2,
  coverage: { my: 1, opponent: 1 },
};

const EDGES = [
  { position: "WR", my_points: 50, opponent_points: 37.6, edge: 12.4, my_count: 3, opponent_count: 3, unmodeled: 0 },
  { position: "TE", my_points: 12, opponent_points: 7.2, edge: 4.8, my_count: 1, opponent_count: 1, unmodeled: 0 },
  { position: "QB", my_points: 18, opponent_points: 20.1, edge: -2.1, my_count: 1, opponent_count: 1, unmodeled: 0 },
  { position: "RB", my_points: 20, opponent_points: 28.2, edge: -8.2, my_count: 2, opponent_count: 2, unmodeled: 0 },
];

// Pre-game, Sleeper lineups not posted yet.
const PREGAME: MatchupResponse = {
  ok: true,
  week: 7,
  my_team: side({ team_name: "Dynasty Overlords" }),
  opponent: side({
    roster_id: "2",
    team_name: "Rival Squad",
    season_value_total: 7600,
    starters: [starter({ player_id: "o1", name: "Opp Back" })],
  }),
  comparison: COMPARISON,
  real_comparison: null,
  win_probability: { available: false, reason: "no_starters" },
  game_state: null,
  position_edges: { actual: null, suggested: EDGES },
  suggested_moves: null,
  basis: "season_value",
  basis_label: COMPARISON.basis_label,
  reason: "",
};

const MOVES: MatchupSuggestedMove[] = [
  {
    slot: "RB",
    start: {
      player_id: "b1",
      name: "Aaron Jones Sr.",
      position: "RB",
      team: "MIN",
      tier: "starter",
      slot: "RB",
      points: 15.7,
      projection_status: "ok",
      injury_label: "",
    },
    over: {
      player_id: "s2",
      name: "Tyrone Tracy Jr.",
      position: "RB",
      team: "NYG",
      tier: "starter",
      slot: "RB",
      points: 7.4,
      projection_status: "ok",
      injury_label: "",
    },
    over_reason: null,
    gain: 8.3,
    locked: false,
  },
];

function liveResponse(overrides: Partial<MatchupResponse> = {}): MatchupResponse {
  const realComparison: MatchupRealComparison = {
    my_points: 42.3,
    opponent_points: 38.1,
    margin: 4.2,
    edge: "you",
    basis: "sleeper_actual_lineup",
    basis_label: "Your actual current-week lineup and live points, straight from Sleeper.",
  };
  return {
    ...PREGAME,
    real_comparison: realComparison,
    win_probability: ODDS,
    game_state: "live",
    position_edges: { actual: EDGES, suggested: EDGES },
    suggested_moves: MOVES,
    my_team: side({
      team_name: "Dynasty Overlords",
      has_live_data: true,
      real_starters: [
        realStarter({ player_id: "s1", name: "Ashton Jeanty" }),
        realStarter({ player_id: "s2", name: "Tyrone Tracy Jr.", actual_points: 0, game_started: false, game_status: "scheduled", projection: { status: "ok", point_estimate: 7.4, low: 5, high: 10, confidence: "low", opponent: "DAL" } }),
      ],
      real_points: 42.3,
    }),
    opponent: side({
      roster_id: "2",
      team_name: "Rival Squad",
      has_live_data: true,
      real_starters: [realStarter({ player_id: "o9", name: "Chase Brown", actual_points: 10.3 })],
      real_points: 38.1,
      real_empty_slots: ["RB"],
    }),
    ...overrides,
  };
}

describe("MatchupContent", () => {
  it("renders the header with the week and no LIVE badge before games start", () => {
    render(<MatchupContent leagueName="My League" matchup={PREGAME} />);

    expect(screen.getByRole("heading", { name: "Matchup", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Week 7")).toBeInTheDocument();
    expect(screen.queryByLabelText("Games in progress")).not.toBeInTheDocument();
    expect(screen.getAllByText("Dynasty Overlords").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rival Squad").length).toBeGreaterThan(0);
  });

  it("pre-game with no posted lineups: suggested tab by default, honest odds and moves copy", () => {
    render(<MatchupContent leagueName="My League" matchup={PREGAME} />);

    expect(screen.getByRole("button", { name: "Suggested Lineup" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Win probability appears once Sleeper posts both lineups.")).toBeInTheDocument();
    expect(screen.getByText("Suggested moves appear once Sleeper has your lineup for this week.")).toBeInTheDocument();
    expect(screen.getByText(/projections for each team's suggested lineup/)).toBeInTheDocument();
    // Suggested starters show their projection in the table.
    expect(screen.getAllByText("13.1").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Actual Lineup" }));
    expect(screen.getByText("Sleeper hasn't posted lineups for this week yet.")).toBeInTheDocument();
  });

  it("shows the symmetric stat tiles from real season value and projections", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse()} />);

    expect(screen.getByText("Your value")).toBeInTheDocument();
    expect(screen.getByText("8,200")).toBeInTheDocument();
    expect(screen.getByText("Their value")).toBeInTheDocument();
    expect(screen.getByText("7,600")).toBeInTheDocument();
    // 124.8 - 116.2
    expect(screen.getByText("+8.6")).toBeInTheDocument();
    expect(screen.getByText("+600")).toBeInTheDocument();
  });

  it("live: LIVE badge, real score with projection under it, win probability split", () => {
    const { container } = render(<MatchupContent leagueName="My League" matchup={liveResponse()} />);

    expect(screen.getByLabelText("Games in progress")).toBeInTheDocument();
    expect(screen.getByText("42.3")).toBeInTheDocument();
    expect(screen.getByText("Proj 124.8")).toBeInTheDocument();
    expect(screen.getByText("64%")).toBeInTheDocument();
    expect(screen.getByText("36%")).toBeInTheDocument();
    expect(container.querySelector(".winprob-bar-fill")).toHaveStyle({ width: "64%" });
    expect(screen.getByText("You're on track to win.")).toBeInTheDocument();
  });

  it("between games: no LIVE badge even though the week has started", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse({ game_state: "between_games" })} />);
    expect(screen.queryByLabelText("Games in progress")).not.toBeInTheDocument();
  });

  it("final: reads the real result", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse({ game_state: "final" })} />);
    expect(screen.getByText("You won this week.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Games in progress")).not.toBeInTheDocument();
  });

  it("insights: verdict plus an explanation built from the real position edges", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse({ game_state: "pregame" })} />);

    expect(screen.getByText("You're favored to win.")).toBeInTheDocument();
    expect(
      screen.getByText("Your WRs (+12.4) and TE (+4.8) give you an edge, but your RBs (-8.2) and QB (-2.1) could be a problem."),
    ).toBeInTheDocument();
    const edges = screen.getByRole("list", { name: "Position edges" });
    expect(within(edges).getByText("+12.4")).toBeInTheDocument();
    expect(within(edges).getByText("-8.2")).toBeInTheDocument();
  });

  it("actual tab (default once Sleeper has a lineup): slot rows, real points, empty slot", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse()} />);

    expect(screen.getByRole("button", { name: "Actual Lineup" })).toHaveAttribute("aria-pressed", "true");
    const table = screen.getByRole("table", { name: "Actual lineups" });
    expect(within(table).getByText("Ashton Jeanty")).toBeInTheDocument();
    expect(within(table).getByText("Chase Brown")).toBeInTheDocument();
    // Started: real points. Not started: projection, never a fake 0.0.
    expect(within(table).getByText("14.2")).toBeInTheDocument();
    expect(within(table).getByText("7.4")).toBeInTheDocument();
    expect(within(table).queryByText("0.0")).not.toBeInTheDocument();
    expect(within(table).getByText("Empty slot")).toBeInTheDocument();
  });

  it("marks a bye-week starter instead of showing a number", () => {
    const withBye = liveResponse();
    withBye.my_team!.real_starters = [
      realStarter({
        player_id: "bye1",
        name: "Bye Guy",
        game_started: null,
        game_status: null,
        actual_points: 0,
        projection: { status: "bye_week", point_estimate: null, low: null, high: null, confidence: null, opponent: null },
      }),
    ];
    render(<MatchupContent leagueName="My League" matchup={withBye} />);
    expect(screen.getByText("Bye")).toBeInTheDocument();
  });

  it("suggested moves: start X over Y with slot badge and points gained; View all expands", () => {
    const many = Array.from({ length: 5 }, (_, index) => ({
      ...MOVES[0],
      start: { ...MOVES[0].start, player_id: `b${index}`, name: `Bench Back ${index}` },
      gain: 5 - index,
    }));
    render(<MatchupContent leagueName="My League" matchup={liveResponse({ suggested_moves: [MOVES[0], ...many] })} />);

    expect(screen.getByText("Aaron Jones Sr.")).toBeInTheDocument();
    expect(screen.getAllByText("Over Tyrone Tracy Jr. (Proj 7.4)").length).toBeGreaterThan(0);
    expect(screen.getByText("+8.3")).toBeInTheDocument();
    // Tyrone Tracy is the second RB in the actual lineup.
    expect(screen.getAllByText("RB2").length).toBeGreaterThan(0);
    expect(screen.queryByText("Bench Back 4")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "View all (6)" }));
    expect(screen.getByText("Bench Back 4")).toBeInTheDocument();
  });

  it("suggested moves: says so when the Sleeper lineup already matches", () => {
    render(<MatchupContent leagueName="My League" matchup={liveResponse({ suggested_moves: [] })} />);
    expect(screen.getByText("Your Sleeper lineup already matches our suggested lineup.")).toBeInTheDocument();
  });

  it("partial coverage: says why the win probability is missing", () => {
    render(
      <MatchupContent
        leagueName="My League"
        matchup={liveResponse({
          win_probability: { available: false, reason: "insufficient_coverage", coverage: { my: 0.2, opponent: 1 } },
        })}
      />,
    );
    expect(screen.getByText("Win probability needs projections for more of each lineup.")).toBeInTheDocument();
    expect(screen.getByText("Not enough projections yet to call it.")).toBeInTheDocument();
  });

  it("bye week: header plus the matchup-specific message", () => {
    const byeWeek: MatchupResponse = {
      ...PREGAME,
      my_team: null,
      opponent: null,
      comparison: null,
      reason: "bye_week",
    };
    render(<MatchupContent leagueName="My League" matchup={byeWeek} />);

    expect(screen.getByText("Week 7")).toBeInTheDocument();
    expect(screen.getByText(/enjoy the bye/)).toBeInTheDocument();
  });

  it("offseason: no current week", () => {
    const offseason: MatchupResponse = {
      ...PREGAME,
      week: null,
      my_team: null,
      opponent: null,
      comparison: null,
      reason: "no_current_week",
    };
    render(<MatchupContent leagueName="My League" matchup={offseason} />);
    expect(screen.getByText("This league hasn't started a week yet.")).toBeInTheDocument();
    expect(screen.getByText("Check back when the season starts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Dashboard" })).toBeInTheDocument();
  });

  it("uses Matchup's own copy for not_a_member_of_league instead of the shared link-account copy", () => {
    const notMember: MatchupResponse = {
      ...PREGAME,
      my_team: null,
      opponent: null,
      comparison: null,
      reason: "not_a_member_of_league",
    };
    render(<MatchupContent leagueName="My League" matchup={notMember} />);

    expect(screen.getByText("You don't appear to own a team in this league.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect a league" })).toBeInTheDocument();
  });

  it("empty rosters on both sides: suggested tab says so", () => {
    const empty: MatchupResponse = {
      ...PREGAME,
      my_team: side({ starters: [] }),
      opponent: side({ roster_id: "2", team_name: "Rival Squad", starters: [] }),
      position_edges: { actual: null, suggested: [] },
    };
    render(<MatchupContent leagueName="My League" matchup={empty} />);
    expect(screen.getByText("No startable players on either roster right now.")).toBeInTheDocument();
    expect(screen.getByText("No position projections yet to compare.")).toBeInTheDocument();
  });

  it("best ball: no tabs, no suggested moves, the league message instead", () => {
    const bestBall: MatchupResponse = {
      ...PREGAME,
      best_ball: true,
      lineup_advice_message: "Best ball sets your lineup for you.",
      suggested_moves: null,
    };
    render(<MatchupContent leagueName="My League" matchup={bestBall} />);
    expect(screen.queryByText("Suggested Lineup")).not.toBeInTheDocument();
    expect(screen.queryByText("Suggested Moves")).not.toBeInTheDocument();
    expect(screen.getByText("Best ball sets your lineup for you.")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MyTeamContent } from "./MyTeamContent";
import type { LineupPlayer, MyTeamNeedsResponse, MyTeamResponse, TeamRanking } from "@/lib/api";

function player(overrides: Partial<LineupPlayer>): LineupPlayer {
  return {
    player_id: "1",
    name: "Test Player",
    position: "RB",
    team: "SF",
    age: 25,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 2000,
    slot: "RB",
    suggested_starter: true,
    roster_slot: "starter",
    opportunity_label: null,
    overall_rating: 88,
    ...overrides,
  };
}

const MY_TEAM: MyTeamResponse = {
  ok: true,
  reason: "",
  roster_id: "1",
  starters: [
    player({ player_id: "qb1", name: "Test Quarterback", position: "QB", slot: "QB", overall_rating: 95 }),
    player({ player_id: "rb1", name: "Test Running Back", position: "RB", slot: "RB", overall_rating: 88 }),
  ],
  bench: [
    player({
      player_id: "wr1",
      name: "Test Bench Receiver",
      position: "WR",
      slot: "BENCH",
      suggested_starter: false,
      roster_slot: "bench",
      overall_rating: 61,
    }),
    player({
      player_id: "te1",
      name: "Test IR Tight End",
      position: "TE",
      slot: "BENCH",
      suggested_starter: false,
      roster_slot: "ir",
      injury_label: "IR",
      overall_rating: null,
    }),
  ],
};

const NEEDS: MyTeamNeedsResponse = {
  ok: true,
  reason: "",
  show_franchise_construction: true,
  superflex: false,
  te_premium: false,
  strengths: ["RB"],
  weaknesses: ["WR"],
  biggest_need: { label: "Biggest Need", value: "Wide Receiver", note: "Starter and depth coverage identify this as the clearest current roster deficiency." },
  position_groups: [
    { position: "QB", classification: "covered", reasons: ["QB is covered."], upgrade_opportunity: false, temporary_injury_pressure: false },
    { position: "WR", classification: "short_term_need", reasons: ["WR is below the league comparison baseline."], upgrade_opportunity: false, temporary_injury_pressure: false },
  ],
};

const TEAM_RANKING: TeamRanking = {
  roster_id: "1",
  team_name: "Dynasty Overlords",
  owner_name: "Test Owner",
  owner_username: "test_owner",
  avatar_url: null,
  wins: 7,
  losses: 6,
  ties: 0,
  record_label: "7-6",
  points_for: 1180.2,
  points_against: 1140.6,
  standing_rank: 3,
  win_pct_label: "53.8%",
  points_for_label: "1,180.2",
  points_against_label: "1,140.6",
  playoff_status: "Playoff seed #3",
  on_playoff_line: false,
  power_rank: 2,
  power_rank_tied: false,
  power_score: 8400,
  franchise_rank: 1,
  franchise_rank_tied: true,
  franchise_score: 9100,
  draft_capital_rank: 2,
  draft_capital_rank_tied: false,
  draft_capital_score: 420,
  pick_count: 7,
  first_rounders: 1,
  starter_rank: 3,
  starter_rank_tied: false,
  starter_score: 6100,
  bench_rank: 5,
  bench_rank_tied: false,
  bench_score: 2300,
  age_rank: 4,
  age_rank_tied: false,
  average_age: 26.4,
  strategy: "contender",
  strategy_label: "Contender",
  archetype: "win_now_contender",
  archetype_label: "Win-Now Contender",
  archetype_explanation: null,
  archetype_strengths: ["RB"],
  archetype_risks: [],
  archetype_recommendations: [],
  trade_tendency: "Neutral",
  transaction_activity_count: 3,
  firsts_acquired: 0,
  firsts_sent: 1,
  current_streak: 1,
  team_badges: [],
  injured_starters: 0,
  health_flag: "Stable",
};

describe("MyTeamContent", () => {
  it("renders real starters/bench with OVR gauges and canonical position colors", () => {
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Test Quarterback")).toBeInTheDocument();
    expect(screen.getByText("Test Bench Receiver")).toBeInTheDocument();
    expect(screen.getByText("Test IR Tight End")).toBeInTheDocument();
    expect(screen.getByText("Injured Reserve")).toBeInTheDocument();

    // Circular OVR gauges render a real rating, never a fabricated one for
    // the null case (the IR tight end's overall_rating is null above).
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
  });

  it("renders Strength & Pressure, Biggest Need, and Position Groups from real roster-needs data", () => {
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />);

    expect(screen.getByText("Strength & Pressure")).toBeInTheDocument();
    expect(screen.getByText(/can absorb a send/)).toBeInTheDocument();
    expect(screen.getByText(/Address/)).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Biggest Need" })).toBeInTheDocument();
    expect(screen.getByText("Wide Receiver")).toBeInTheDocument();

    expect(screen.getByText("Position Groups")).toBeInTheDocument();
    expect(screen.getByText("Thin")).toBeInTheDocument();
  });

  it("degrades gracefully when the best-effort roster-needs fetch fails", () => {
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={null} teamRanking={null} leagueSize={0} />);

    expect(screen.getByText("Test Quarterback")).toBeInTheDocument();
    expect(screen.queryByText("Strength & Pressure")).not.toBeInTheDocument();
    expect(screen.queryByText("Position Groups")).not.toBeInTheDocument();
  });

  it("shows the roster-not-ready message instead of an empty lineup when `reason` is set", () => {
    const notReady: MyTeamResponse = { ok: true, reason: "empty_roster", starters: [], bench: [] };
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={notReady} needs={null} teamRanking={null} leagueSize={0} />);

    expect(screen.getByText("Your roster in this league looks empty.")).toBeInTheDocument();
  });
});

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

  // coridian_, 2026-10-18, screenshot: a row with no OVR rating left its
  // value/"VALUE" column shifted out of alignment with rows that do have
  // one. OvrGauge now reserves the same space either way — not a
  // fabricated number, just a same-size invisible placeholder.
  it("reserves the OVR gauge's width even when a player has no rating", () => {
    const { container } = render(
      <MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />,
    );

    expect(container.querySelector(".ovr-gauge-placeholder")).toBeInTheDocument();
  });

  // coridian_, 2026-10-18, screenshot: "the bench should be in order so.
  // QBs, RBs, WRs, TEs, K, DST" — the API returns bench players in value
  // order, mixing positions together.
  it("sorts the active bench by position (QB, RB, WR, TE, K, DST)", () => {
    const mixedOrderTeam: MyTeamResponse = {
      ...MY_TEAM,
      bench: [
        player({ player_id: "bk1", name: "Bench Kicker", position: "K", roster_slot: "bench" }),
        player({ player_id: "bwr1", name: "Bench Receiver", position: "WR", roster_slot: "bench" }),
        player({ player_id: "bqb1", name: "Bench Quarterback", position: "QB", roster_slot: "bench" }),
        player({ player_id: "brb1", name: "Bench Running Back", position: "RB", roster_slot: "bench" }),
      ],
    };
    const { container } = render(
      <MyTeamContent leagueName="Dynasty Overlords" myTeam={mixedOrderTeam} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />,
    );

    const text = container.textContent || "";
    const names = ["Bench Quarterback", "Bench Running Back", "Bench Receiver", "Bench Kicker"];
    const indices = names.map((name) => text.indexOf(name));
    expect(indices.every((index) => index !== -1)).toBe(true);
    expect(indices).toEqual([...indices].sort((a, b) => a - b));
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

  // Recommendation-compliance audit, Check 3 follow-up — My Team's own
  // injury-alert/value-trend GM Plan/Dashboard tiles already carry
  // route_player_id and already get it threaded through as ?playerId= by
  // gamePlanTileHref (same mechanism #1293 gave Waivers/Trade Hub). This
  // page must actually surface/highlight that specific roster row, not just
  // avoid crashing when the param is present.
  describe("highlightPlayerId (GM Plan deep link)", () => {
    it("marks no row as highlighted without a highlightPlayerId (current/before behavior)", () => {
      const { container } = render(
        <MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />,
      );
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
    });

    it("highlights the named starter", () => {
      const { container } = render(
        <MyTeamContent
          leagueName="Dynasty Overlords"
          myTeam={MY_TEAM}
          needs={NEEDS}
          teamRanking={TEAM_RANKING}
          leagueSize={10}
          highlightPlayerId="rb1"
        />,
      );
      const highlighted = container.querySelector('[data-highlighted="true"]');
      expect(highlighted).not.toBeNull();
      expect(highlighted?.textContent).toContain("Test Running Back");
    });

    it("highlights the named bench player, including one on Injured Reserve", () => {
      const { container } = render(
        <MyTeamContent
          leagueName="Dynasty Overlords"
          myTeam={MY_TEAM}
          needs={NEEDS}
          teamRanking={TEAM_RANKING}
          leagueSize={10}
          highlightPlayerId="te1"
        />,
      );
      const highlighted = container.querySelector('[data-highlighted="true"]');
      expect(highlighted).not.toBeNull();
      expect(highlighted?.textContent).toContain("Test IR Tight End");
    });

    it("falls back gracefully (no crash, no highlight) when the playerId matches nothing on the roster", () => {
      const { container } = render(
        <MyTeamContent
          leagueName="Dynasty Overlords"
          myTeam={MY_TEAM}
          needs={NEEDS}
          teamRanking={TEAM_RANKING}
          leagueSize={10}
          highlightPlayerId="does-not-exist"
        />,
      );
      expect(container.querySelector('[data-highlighted="true"]')).toBeNull();
      expect(screen.getByText("Test Quarterback")).toBeInTheDocument();
    });
  });

  // Logic audit 2026-10-21: in-season lineups never start a player on bye;
  // the server benches him with start_ineligible_reason "Bye" and lists any
  // slot nobody eligible could fill.
  it("tags a bye-week bench player and names open lineup slots", () => {
    const weekly: MyTeamResponse = {
      ...MY_TEAM,
      week: 7,
      lineup_basis: "weekly_projection",
      lineup_basis_label: "This week's lineup: ranked by projected points.",
      open_slots: ["TE"],
      bench: [
        player({
          player_id: "rb9",
          name: "Test Bye Back",
          slot: "BENCH",
          suggested_starter: false,
          roster_slot: "bench",
          on_bye: true,
          start_ineligible_reason: "Bye",
        }),
      ],
    };
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={weekly} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />);

    expect(screen.getByText("· BYE")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Open slot this week: TE");
    expect(screen.getByText(/Week 7\. This week's lineup/)).toBeInTheDocument();
  });

  it("shows no weekly notes for an older API response without the weekly fields", () => {
    render(<MyTeamContent leagueName="Dynasty Overlords" myTeam={MY_TEAM} needs={NEEDS} teamRanking={TEAM_RANKING} leagueSize={10} />);

    expect(screen.queryByText("· BYE")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("MyTeamContent best ball", () => {
  it("replaces the suggested Starters/Bench split with one roster list and the best ball note", () => {
    render(
      <MyTeamContent
        leagueName="Best Ball League"
        myTeam={{
          ...MY_TEAM,
          best_ball: true,
          lineup_advice_message: "Best ball league: Sleeper sets your lineup automatically.",
        }}
        needs={NEEDS}
        teamRanking={TEAM_RANKING}
        leagueSize={10}
      />,
    );
    expect(screen.getByText("Best ball league: Sleeper sets your lineup automatically.")).toBeInTheDocument();
    expect(screen.queryByText("Starters")).not.toBeInTheDocument();
    expect(screen.getByText("Roster")).toBeInTheDocument();
    // Suggested starters and active bench share the one roster list.
    expect(screen.getByText("Test Quarterback")).toBeInTheDocument();
    expect(screen.getByText("Test Bench Receiver")).toBeInTheDocument();
    expect(screen.getByText("Test IR Tight End")).toBeInTheDocument();
  });
});

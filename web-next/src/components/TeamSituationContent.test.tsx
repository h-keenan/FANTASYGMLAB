import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TeamSituationContent } from "./TeamSituationContent";
import type { GmTarget, LineupPlayer, MyTeamResponse, TeamStanceResponse } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      setTeamStance: vi.fn().mockResolvedValue({ ok: true, stance: "competing" }),
      addGmTarget: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      setGmTargetUntouchable: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
    },
  };
});

function player(overrides: Partial<LineupPlayer>): LineupPlayer {
  return {
    player_id: "p1",
    name: "Test Player",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    injury_label: "",
    ruled_out: false,
    tier: "starter",
    score: 1500,
    slot: "WR1",
    suggested_starter: true,
    opportunity_label: null,
    overall_rating: 72,
    ...overrides,
  };
}

function target(overrides: Partial<GmTarget>): GmTarget {
  return {
    player_id: "p1",
    source_surface: "team_stance",
    created_at: "2026-10-01T00:00:00Z",
    untouchable: false,
    ...overrides,
  };
}

const MY_TEAM: MyTeamResponse = {
  ok: true,
  starters: [player({})],
  bench: [player({ player_id: "p2", name: "Bench Guy", position: "RB" })],
  reason: "",
};

const STANCE: TeamStanceResponse = { ok: true, stance: "rebuilding", strategy: "rebuild" };

describe("TeamSituationContent", () => {
  it("renders the league name and the declared stance option", () => {
    render(
      <TeamSituationContent leagueId="league-1" leagueName="Dynasty Overlords" teamStance={STANCE} myTeam={MY_TEAM} targets={[]} />,
    );

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rebuilding", pressed: true })).toBeInTheDocument();
    expect(screen.getByText("Prioritize youth and future draft capital")).toBeInTheDocument();
  });

  it("calls setTeamStance when a different stance is picked", () => {
    render(
      <TeamSituationContent leagueId="league-1" leagueName="Dynasty Overlords" teamStance={STANCE} myTeam={MY_TEAM} targets={[]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Competing" }));

    expect(api.setTeamStance).toHaveBeenCalledWith("league-1", "competing");
  });

  it("lists roster players and groups an already-untouchable one under Protected Players", () => {
    render(
      <TeamSituationContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        teamStance={STANCE}
        myTeam={MY_TEAM}
        targets={[target({ untouchable: true })]}
      />,
    );

    expect(screen.getByText("Test Player")).toBeInTheDocument();
    expect(screen.getByText("Bench Guy")).toBeInTheDocument();
    expect(screen.getByText("Rest of Roster")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Protected" })).toBeInTheDocument();
  });

  it("adds a GM Target then marks it untouchable when protecting a player not yet tracked", async () => {
    render(
      <TeamSituationContent leagueId="league-1" leagueName="Dynasty Overlords" teamStance={STANCE} myTeam={MY_TEAM} targets={[]} />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Protect" })[0]);

    expect(api.addGmTarget).toHaveBeenCalledWith("league-1", "p1", "team_stance");
    await screen.findByRole("button", { name: "Protected" });
    expect(api.setGmTargetUntouchable).toHaveBeenCalledWith("league-1", "p1", true);
  });

  it("shows a no-roster message when the league has no roster players", () => {
    render(
      <TeamSituationContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        teamStance={STANCE}
        myTeam={{ ok: true, starters: [], bench: [], reason: "empty_roster" }}
        targets={[]}
      />,
    );

    expect(screen.getByText("No roster players found for this league.")).toBeInTheDocument();
  });
});

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimLeaguePlayersView, SimLeagueTeamsView } from "./SimLeagueWho";
import { SimTeamCard } from "./SimTeamCard";
import type { SimCtx } from "./SimGameParts";
import type { SimGamePlayer, SimLeagueRosterTeam } from "@/lib/simGame";
import type { SimLeagueRostersState } from "@/lib/useSimLeagueRosters";

function p(id: string, pos: SimGamePlayer["pos"], name: string, value: number, owner: string, over: Partial<SimGamePlayer> = {}): SimGamePlayer {
  return { id, name, pos, team: "KC", age: 25, adp: 5, value, projection: 12.3, floor: 5, ceiling: 20, status: "healthy", out_weeks: 0, bye_week: 9, owner: { type: "ai", team_id: owner, name: owner }, squad: "roster", ...over };
}

function team(id: string, name: string, power: number, players: SimGamePlayer[], over: Partial<SimLeagueRosterTeam> = {}): SimLeagueRosterTeam {
  return {
    team_id: id, name, is_you: false, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." }, power_rank: power, avg_age: 25, roster_size: players.length,
    record: { wins: 3, losses: 0, ties: 0, pf: 269.4, pa: 200, rank: power, streak: "W3", seed: null, playoff_status: "in" } as SimLeagueRosterTeam["record"],
    positions: [], strengths: ["QB"], needs: ["RB"], surplus: ["WR"], top_assets: players.slice(0, 3), players, ...over,
  };
}

const teams = [
  team("1", "Bench Mob", 2, [p("q1", "QB", "Quinn Back", 90, "1"), p("r1", "RB", "Ray Runner", 40, "1", { value: 0 })]),
  team("2", "Goal Line Gamblers", 1, [p("q2", "QB", "Quentin Arm", 70, "2"), p("w1", "WR", "Wes Wide", 60, "2", { status: "out", out_weeks: 3, projection: 0 })]),
  team("3", "Me", 3, [p("t1", "TE", "Tom Tight", 50, "3")], { is_you: true }),
];
const ready: SimLeagueRostersState = { status: "ready", teams };

function ctx() {
  return { openTeam: vi.fn(), openPlayer: vi.fn() } as unknown as SimCtx & { openTeam: ReturnType<typeof vi.fn>; openPlayer: ReturnType<typeof vi.fn> };
}

describe("league Teams view (shared team card)", () => {
  it("lists every team best power first with record, top assets and need / deep chips, and a tap opens its roster", () => {
    const c = ctx();
    render(<SimLeagueTeamsView ctx={c} state={ready} onRetry={() => {}} />);
    const cards = screen.getAllByTestId("sim-team-card");
    expect(cards).toHaveLength(3);
    expect(cards[0]).toHaveTextContent("Goal Line Gamblers");
    expect(cards[0]).toHaveTextContent("3-0 · #1 · 269.4 PF");
    expect(cards[0]).toHaveTextContent("Needs RB");
    expect(cards[0]).toHaveTextContent("Deep WR");
    expect(cards[0]).toHaveTextContent("Quentin Arm");
    expect(cards[0]).toHaveTextContent("VAL 70");
    expect(cards[1]).toHaveTextContent("Bench Mob");
    expect(cards[1]).toHaveTextContent("VAL —"); // no market value is a dash, never 0
    fireEvent.click(screen.getByRole("button", { name: "Bench Mob. Open roster" }));
    expect(c.openTeam).toHaveBeenCalledWith("1");
  });

  it("shows a skeleton while loading and a retry when the request failed", () => {
    const retry = vi.fn();
    const { rerender } = render(<SimLeagueTeamsView ctx={ctx()} state={{ status: "loading" }} onRetry={retry} />);
    expect(screen.queryByTestId("sim-team-card")).toBeNull();
    rerender(<SimLeagueTeamsView ctx={ctx()} state={{ status: "error" }} onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });
});

describe("league Players view (find a player, position by position)", () => {
  it("lists rostered players best value first, each with its owner and labeled stats", () => {
    render(<SimLeaguePlayersView ctx={ctx()} state={ready} onRetry={() => {}} />);
    const rows = screen.getAllByTestId("sim-player-line");
    expect(rows.map((r) => within(r).getByText(/Quinn Back|Quentin Arm|Wes Wide|Tom Tight|Ray Runner/).textContent)).toEqual(["Quinn Back", "Quentin Arm", "Wes Wide", "Tom Tight", "Ray Runner"]);
    expect(rows[0]).toHaveTextContent("PROJ");
    expect(rows[0]).toHaveTextContent("VAL");
    expect(rows[0]).toHaveTextContent("Bench Mob");
    expect(rows[4]).toHaveTextContent("—"); // zero value shown as a dash
    expect(rows[3]).toHaveTextContent("Your team");
    expect(rows[2]).toHaveTextContent("OUT");
  });

  it("position pills show all QBs (or any position) with their owners", () => {
    render(<SimLeaguePlayersView ctx={ctx()} state={ready} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("tab", { name: "QB" }));
    const rows = screen.getAllByTestId("sim-player-line");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Quinn Back");
    expect(rows[1]).toHaveTextContent("Goal Line Gamblers");
    expect(screen.getByText(/2 players at QB/)).toBeInTheDocument();
  });

  it("find a player by name; tapping the owner opens that team, tapping the row opens the player", () => {
    const c = ctx();
    render(<SimLeaguePlayersView ctx={c} state={ready} onRetry={() => {}} />);
    fireEvent.change(screen.getByLabelText("Find a player"), { target: { value: "wes" } });
    const rows = screen.getAllByTestId("sim-player-line");
    expect(rows).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Owned by Goal Line Gamblers. Open team" }));
    expect(c.openTeam).toHaveBeenCalledWith("2");
    expect(c.openPlayer).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Wes Wide, WR\. Open player details/ }));
    expect(c.openPlayer).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Find a player"), { target: { value: "zzz" } });
    expect(screen.getByText("No one matches")).toBeInTheDocument();
  });
});

describe("SimTeamCard", () => {
  it("is not a button without onOpen (the selected partner card) and carries no chips when the team is balanced", () => {
    render(<SimTeamCard team={team("9", "Even Steven", 5, [], { needs: [], surplus: [] })} selected />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByLabelText("Needs and depth")).toBeNull();
  });
});

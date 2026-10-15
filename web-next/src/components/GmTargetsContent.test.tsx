import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GmTargetsContent } from "./GmTargetsContent";
import type { GmTarget, GmTargetsResponse, LeagueRankingsResponse, RankedPlayer } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      removeGmTarget: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      setGmTargetUntouchable: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
    },
  };
});

function target(overrides: Partial<GmTarget>): GmTarget {
  return {
    player_id: "p1",
    source_surface: "player_quick_view",
    created_at: "2026-10-01T00:00:00Z",
    untouchable: false,
    ...overrides,
  };
}

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Test Target",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 12,
    position_rank: 4,
    rank_unavailable_reason: null,
    opportunity_label: "Lead Receiver",
    overall_rating: 72,
    ...overrides,
  };
}

const TARGETS: GmTargetsResponse = { ok: true, targets: [target({})] };
const RANKINGS: LeagueRankingsResponse = { ok: true, players: [player({})] };

describe("GmTargetsContent", () => {
  it("renders the league name and the target's identity/score/rank", () => {
    render(<GmTargetsContent leagueId="league-1" leagueName="Dynasty Overlords" targets={TARGETS} rankings={RANKINGS} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Test Target")).toBeInTheDocument();
    expect(screen.getByText("1500")).toBeInTheDocument();
    expect(screen.getByText("WR4")).toBeInTheDocument();
    expect(screen.getByText(/Added from Player Quick View/)).toBeInTheDocument();
  });

  it("groups untouchable targets separately from watching targets", () => {
    const data: GmTargetsResponse = {
      ok: true,
      targets: [target({ player_id: "p1", untouchable: true }), target({ player_id: "p2", untouchable: false })],
    };
    const rankings: LeagueRankingsResponse = {
      ok: true,
      players: [player({ player_id: "p1", name: "Protected Player" }), player({ player_id: "p2", name: "Watched Player" })],
    };
    render(<GmTargetsContent leagueId="league-1" leagueName="Dynasty Overlords" targets={data} rankings={rankings} />);

    expect(screen.getByText("Untouchable")).toBeInTheDocument();
    expect(screen.getByText("Watching")).toBeInTheDocument();
    expect(screen.getByText("Protected Player")).toBeInTheDocument();
    expect(screen.getByText("Watched Player")).toBeInTheDocument();
  });

  it("shows a fallback name and context line for a target not on the current rankings board", () => {
    const data: GmTargetsResponse = { ok: true, targets: [target({ player_id: "p9" })] };
    const rankings: LeagueRankingsResponse = { ok: true, players: [] };
    render(<GmTargetsContent leagueId="league-1" leagueName="Dynasty Overlords" targets={data} rankings={rankings} />);

    expect(screen.getByText("Player p9")).toBeInTheDocument();
    expect(screen.getByText(/Not on the current rankings board/)).toBeInTheDocument();
  });

  it("calls setGmTargetUntouchable when the untouchable toggle is pressed", () => {
    render(<GmTargetsContent leagueId="league-1" leagueName="Dynasty Overlords" targets={TARGETS} rankings={RANKINGS} />);

    fireEvent.click(screen.getByRole("button", { name: "Mark untouchable" }));

    expect(api.setGmTargetUntouchable).toHaveBeenCalledWith("league-1", "p1", true);
    expect(screen.getByRole("button", { name: "Unmark untouchable" })).toBeInTheDocument();
  });

  it("calls removeGmTarget and optimistically removes the row when Remove is pressed", () => {
    render(<GmTargetsContent leagueId="league-1" leagueName="Dynasty Overlords" targets={TARGETS} rankings={RANKINGS} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(api.removeGmTarget).toHaveBeenCalledWith("league-1", "p1");
    expect(screen.queryByText("Test Target")).not.toBeInTheDocument();
  });

  it("shows the empty state with a link to Players when there are no targets", () => {
    render(
      <GmTargetsContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        targets={{ ok: true, targets: [] }}
        rankings={{ ok: true, players: [] }}
      />,
    );

    expect(screen.getByText(/No GM Targets yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Players/ })).toBeInTheDocument();
  });
});

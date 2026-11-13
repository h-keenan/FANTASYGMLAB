import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptySlotCard, PlayerCard } from "./PlayerCardKit";
import { playerCardFromStarter, type PlayerCardSource } from "@/lib/playerCard";

const live: PlayerCardSource = {
  player_id: "1",
  name: "Cam Skattebo",
  position: "RB",
  team: "NYG",
  tier: "Core Starter",
  overall_rating: 81,
  game_status: "in_progress",
  game_started: true,
  actual_points: 11.2,
  projected_final: 17.4,
  game_progress: 0.55,
  game_opponent: "DAL",
  game_is_home: false,
  projection: { status: "ok", point_estimate: 14, opponent: "DAL" },
};

describe("PlayerCard variants", () => {
  it("matchup: points, status chip, game line, trend, progress and expandable detail", () => {
    render(<PlayerCard variant="matchup" model={playerCardFromStarter(live)} emphasis="win" />);
    expect(screen.getByTestId("player-card-points")).toHaveTextContent("11.2");
    expect(screen.getByTestId("player-chip-live")).toBeInTheDocument();
    expect(screen.getByTestId("player-card-game-line")).toHaveTextContent("NYG · @ DAL · ~Q3");
    const proj = screen.getByTestId("proj-final");
    expect(proj).toHaveTextContent("Proj final 17.4");
    expect(proj.style.color).toBe("var(--color-success)");
    expect(screen.getByRole("progressbar", { name: "Game progress" })).toHaveAttribute("aria-valuenow", "55");
    expect(screen.getByTestId("player-card-matchup")).toHaveAttribute("data-emphasis", "win");

    expect(screen.queryByTestId("player-card-detail")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show Cam Skattebo details" }));
    expect(screen.getByTestId("player-card-detail")).toHaveTextContent("Pre-game projection");
  });

  it("matchup: a falling projected final is red, and a pre-kickoff card shows the projection with UPCOMING", () => {
    const { unmount } = render(
      <PlayerCard variant="matchup" model={playerCardFromStarter({ ...live, projected_final: 8 })} />,
    );
    expect(screen.getByTestId("proj-final").style.color).toBe("var(--color-danger)");
    unmount();
    render(
      <PlayerCard
        variant="matchup"
        model={playerCardFromStarter({ ...live, game_status: "scheduled", game_started: false, actual_points: 0 })}
      />,
    );
    expect(screen.getByTestId("player-chip-upcoming")).toBeInTheDocument();
    expect(screen.getByTestId("player-card-points")).toHaveTextContent("14.0");
    expect(screen.queryByTestId("proj-final")).not.toBeInTheDocument();
  });

  it("matchup: bye and out players are flagged, never a fake number", () => {
    const { unmount } = render(
      <PlayerCard
        variant="matchup"
        model={playerCardFromStarter({ ...live, game_status: null, game_started: null, projection: { status: "bye_week", point_estimate: null } })}
      />,
    );
    expect(screen.getByTestId("player-chip-bye")).toBeInTheDocument();
    expect(screen.getByTestId("player-card-matchup")).toHaveAttribute("data-unavailable", "true");
    unmount();
    render(<PlayerCard variant="matchup" model={playerCardFromStarter({ ...live, game_status: "scheduled", game_started: false, injury_label: "Out" })} />);
    expect(screen.getByTestId("player-chip-out")).toBeInTheDocument();
  });

  it("matchup: bumping pulseKey mounts the pulse overlay", () => {
    const model = playerCardFromStarter(live);
    const { rerender } = render(<PlayerCard variant="matchup" model={model} pulseKey={0} />);
    expect(screen.queryByTestId("player-card-pulse")).not.toBeInTheDocument();
    rerender(<PlayerCard variant="matchup" model={model} pulseKey={1} />);
    expect(screen.getByTestId("player-card-pulse")).toBeInTheDocument();
  });

  it("compact: photo slot, name, position, team, chips and up to two stats", () => {
    render(
      <PlayerCard
        variant="compact"
        model={playerCardFromStarter({ ...live, game_status: "scheduled", game_started: false, injury_label: "Questionable" })}
        stats={[{ label: "Proj", value: "14.0" }, { label: "Value", value: "81" }, { label: "Extra", value: "9" }]}
      />,
    );
    expect(screen.getByTestId("player-card-compact")).toHaveTextContent("Cam Skattebo");
    expect(screen.getByTestId("player-card-compact")).toHaveTextContent("NYG");
    expect(screen.getByTestId("player-chip-questionable")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
    expect(screen.queryByText("Extra")).not.toBeInTheDocument();
  });

  it("card: tile with value ring and stats", () => {
    render(<PlayerCard variant="card" model={playerCardFromStarter(live)} stats={[{ label: "Proj", value: "14.0" }]} />);
    expect(screen.getByTestId("player-card-tile")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "81 overall rating" })).toBeInTheDocument();
  });

  it("empty slot card offers a fill action in planner mode", () => {
    let called = false;
    render(<EmptySlotCard onEdit={() => (called = true)} />);
    fireEvent.click(screen.getByRole("button", { name: "Empty, tap to fill" }));
    expect(called).toBe(true);
  });
});

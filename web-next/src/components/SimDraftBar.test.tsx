import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimDraftBar } from "./SimDraftBar";
import { SimRecentStrip } from "./SimDraftOverview";
import { CompactModule } from "@/components/ui/CompactModule";

const model = { playerId: "9509", name: "Jahmyr Gibbs", position: "RB", team: "DET", adp: "ADP 5", grade: "A-", fit: "Fills your RB need" };

describe("SimDraftBar", () => {
  it("shows avatar, position and letter grade on the collapsed clock, and opens the player", () => {
    const onOpen = vi.fn();
    render(
      <CompactModule id="t.clock" title="Draft clock" persist={false} parts={[{ key: "a", text: "R4 P7" }, { key: "b", text: "You pick now" }]} preview={<SimDraftBar model={model} onOpen={onOpen} grade={{ grade: "A-" }} />}>
        <p>on the clock body</p>
      </CompactModule>,
    );
    expect(screen.queryByText("on the clock body")).toBeNull();
    const bar = screen.getByTestId("draft-bar-player");
    expect(bar.querySelector("img")).not.toBeNull();
    expect(bar).toHaveTextContent("Jahmyr Gibbs");
    expect(bar).toHaveTextContent("RB");
    expect(screen.getByTestId("letter-grade")).toHaveTextContent("A-");
    fireEvent.click(bar);
    expect(onOpen).toHaveBeenCalled();
  });
  it("without a grade the bar keeps ADP, and never renders a bare number rating", () => {
    render(<SimDraftBar model={{ ...model, grade: null }} grade={null} />);
    expect(screen.queryByTestId("letter-grade")).toBeNull();
    expect(screen.getByTestId("draft-bar-player")).toHaveTextContent("ADP 5");
  });
});

describe("SimRecentStrip (recent picks in the pinned clock area)", () => {
  const card = (n: number, name: string, pos: string, team: string | null, grade: string | null) => ({
    key: String(n),
    pickNo: n,
    pickLabel: `#${n}`,
    player: { id: String(n), name, position: pos, team: "KC", headshotId: null },
    grade: grade ? ({ grade } as never) : null,
    teamName: team,
    isYou: false,
    aria: `Pick ${n}: ${name}`,
  });

  it("shows avatar, name, position, letter grade and the picking team's logo per pick, and opens the player", () => {
    const onOpen = vi.fn();
    const onBoard = vi.fn();
    render(<SimRecentStrip cards={[card(7, "Jahmyr Gibbs", "RB", "Dynasty Dogs", "A-"), card(6, "Zay Flowers", "WR", "Rivals", null)]} onOpenPlayer={onOpen} onFullBoard={onBoard} />);
    expect(screen.getAllByTestId("recent-pick-card")).toHaveLength(2);
    expect(screen.getAllByTestId("player-avatar-slot")).toHaveLength(2);
    expect(screen.getAllByTestId("sim-team-identity")).toHaveLength(2);
    expect(screen.getAllByTestId("letter-grade")).toHaveLength(1);
    fireEvent.click(screen.getByLabelText("Pick 7: Jahmyr Gibbs"));
    expect(onOpen).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("recent-full-board"));
    expect(onBoard).toHaveBeenCalled();
  });

  it("says so when there are no picks yet", () => {
    render(<SimRecentStrip cards={[]} />);
    expect(screen.getByText(/No picks yet/)).toBeInTheDocument();
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimDraftBar } from "./SimDraftBar";
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

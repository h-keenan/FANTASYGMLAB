import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerListRow } from "./PlayerListRow";

describe("PlayerListRow anatomy", () => {
  it("puts the stat chips and tags under the name (not at the right), wrapping instead of clipping, with one trailing action", () => {
    render(
      <PlayerListRow
        name="Jahmyr Gibbs"
        position="RB"
        meta={[{ key: "team", text: "DET" }, { key: "age", text: "Age 24" }]}
        stats={[{ key: "proj", label: "Proj", value: "12.1" }, { key: "adp", label: "ADP", value: "1.0" }]}
        tags={[{ key: "t1", label: "Hot streak" }, { key: "t2", label: "Waiver target" }, { key: "t3", label: "Bye 6" }]}
        chipsExtra={<button>Queue</button>}
        actions={<button>Draft</button>}
      />,
    );
    const chips = screen.getByTestId("list-chips");
    expect(within(chips).getByText("Proj")).toBeInTheDocument();
    expect(within(chips).getByText("Hot streak")).toBeInTheDocument();
    expect(within(chips).getByText("+1")).toBeInTheDocument();
    expect(within(chips).getByRole("button", { name: "Queue" })).toBeInTheDocument();
    // wraps, never clipped
    expect(chips.className).toContain("flex-wrap");
    expect(chips.className).not.toContain("overflow-hidden");
    expect(screen.getByTestId("list-tags").className).not.toContain("overflow-hidden");
    // exactly one trailing action
    expect(screen.getAllByRole("button", { name: "Draft" })).toHaveLength(1);
  });
});

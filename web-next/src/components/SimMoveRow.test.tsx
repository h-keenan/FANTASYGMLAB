import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimRosterLine, SimRowAccordion } from "./SimGameParts";
import type { SimMoveHandle } from "./SimMoveStrip";
import type { SimGamePlayer } from "@/lib/simGame";
import { simMoveSpecs } from "@/lib/simMove";

const player = (over: Partial<SimGamePlayer> = {}): SimGamePlayer =>
  ({ id: "p1", headshot_id: null, name: "Pat Nacua", pos: "WR", team: "LAR", age: 31, adp: 30, projection: 17.7, ros_mean: 17.7, status: "healthy", out_weeks: 0, bye_week: 11, grade: "A-", squad: "roster", ...over }) as SimGamePlayer;

function handle(p: SimGamePlayer, run = vi.fn()): SimMoveHandle {
  return {
    run,
    specs: simMoveSpecs({
      player: p,
      swapTargets: [{ index: 1, label: "WR2", current: player({ id: "p2", name: "Jo Smith" }) }, { index: 4, label: "FLEX", current: null }],
      canCut: true,
      block: { on: false },
      profile: true,
    }),
  };
}

describe("a roster row with Move", () => {
  it("shows exactly one always-visible trailing control and no Cut / Swap / IR buttons until it is opened", () => {
    render(<SimRosterLine player={player()} move={handle(player())} onOpen={() => {}} />);
    const action = screen.getByTestId("row-action");
    expect(within(action).getAllByRole("button")).toHaveLength(1);
    expect(within(action).getByRole("button", { name: "Move Pat Nacua" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Cut" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Swap in" })).toBeNull();
    // two lines: name line + stats line; the grade is a tile inside the stats line with no "GRADE" word
    expect(screen.getByTestId("row-meta")).toHaveTextContent("LAR · Age 31 · Bye 11 · PROJ 17.7");
    expect(screen.getByTestId("row-meta")).not.toHaveTextContent(/grade/i);
    expect(screen.getByTestId("row-grade")).toHaveAttribute("data-grade", "A-");
  });

  it("opens in place into a strip of only the possible actions with one primary; slot chips run the swap; cut asks first", async () => {
    const run = vi.fn();
    render(<SimRowAccordion><SimRosterLine player={player()} move={handle(player(), run)} onOpen={() => {}} /></SimRowAccordion>);
    fireEvent.click(screen.getByRole("button", { name: "Move Pat Nacua" }));
    const strip = screen.getByTestId("move-strip");
    expect(within(strip).getAllByRole("button").map((b) => b.textContent)).toEqual(["Swap in", "Block", "Profile", "Cut"]); // no IR / taxi: he is healthy
    fireEvent.click(within(strip).getByRole("button", { name: "Swap in" }));
    const chips = within(screen.getByTestId("move-targets"));
    expect(chips.getAllByRole("button").map((b) => b.textContent)).toEqual(["WR2for Smith", "FLEXempty"]);
    fireEvent.click(chips.getByRole("button", { name: /WR2/ }));
    await waitFor(() => expect(run).toHaveBeenCalledWith("swap", "1"));
    fireEvent.click(within(strip).getByRole("button", { name: "Cut" }));
    expect(screen.getByTestId("move-cut-confirm")).toHaveTextContent("Cut Nacua?");
    expect(run).not.toHaveBeenCalledWith("cut", undefined);
    fireEvent.click(within(screen.getByTestId("move-cut-confirm")).getByRole("button", { name: "Cut" }));
    await waitFor(() => expect(run).toHaveBeenCalledWith("cut", undefined));
    // tapping Move again collapses it
    fireEvent.click(screen.getByRole("button", { name: "Move Pat Nacua" }));
    expect(screen.queryByTestId("move-strip")).toBeNull();
  });

  it("Profile in the strip opens the player; a row without Move has no trailing control", () => {
    const onOpen = vi.fn();
    const { rerender } = render(<SimRosterLine player={player()} move={handle(player())} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: "Move Pat Nacua" }));
    fireEvent.click(within(screen.getByTestId("move-strip")).getByRole("button", { name: "Profile" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    rerender(<SimRosterLine player={player({ id: "p9" })} onOpen={onOpen} />);
    expect(screen.queryByTestId("row-action")).toBeNull();
  });
});

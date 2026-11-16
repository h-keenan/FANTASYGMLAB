// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimOpenersProvider, SimPlayerChip, type SimCtx } from "@/components/SimGameParts";
import { PlayerTap } from "@/components/ui/PlayerOpenContext";

function ctxWith(openPlayer: SimCtx["openPlayer"]): SimCtx {
  return { openPlayer, openTeam: vi.fn(), openPick: vi.fn() } as unknown as SimCtx;
}

describe("sim player routing (every sim surface opens the SIM player sheet, never the real-NFL quick view)", () => {
  it("a shared PlayerTap inside the sim opener scope opens the sim sheet by sim id", () => {
    const openPlayer = vi.fn();
    render(
      <SimOpenersProvider ctx={ctxWith(openPlayer)}>
        <PlayerTap player={{ id: "sim-p-17", name: "Fictional Back", position: "RB" }}>Fictional Back</PlayerTap>
      </SimOpenersProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Fictional Back/ }));
    expect(openPlayer).toHaveBeenCalledTimes(1);
    expect(openPlayer.mock.calls[0][0]).toMatchObject({ id: "sim-p-17", name: "Fictional Back", pos: "RB" });
  });

  it("a sim player chip with no explicit handler falls back to the same sim opener", () => {
    const openPlayer = vi.fn();
    render(
      <SimOpenersProvider ctx={ctxWith(openPlayer)}>
        <SimPlayerChip player={{ id: "sim-p-9", name: "Made Up QB", pos: "QB", team: null, age: 24, adp: null, projection: 0 } as never} />
      </SimOpenersProvider>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(openPlayer).toHaveBeenCalledWith(expect.objectContaining({ id: "sim-p-9" }));
  });
});

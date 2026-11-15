import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { PlayerAccordionRow } from "@/components/ui/PlayerAccordionRow";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { PickOpenContext, PlayerOpenContext } from "@/components/ui/PlayerOpenContext";
import { TradeCompactCard } from "@/components/ui/TradeCompactCard";

const chase = { id: "7564", name: "Ja'Marr Chase", position: "WR", team: "CIN", age: 25 };
const rookie = { id: null, name: "Zed Rookie", position: "RB" };

function withOpeners(ui: React.ReactNode, openPlayer = vi.fn(), openPick = vi.fn()) {
  render(
    <PlayerOpenContext.Provider value={openPlayer}>
      <PickOpenContext.Provider value={openPick}>{ui}</PickOpenContext.Provider>
    </PlayerOpenContext.Provider>,
  );
  return { openPlayer, openPick };
}

describe("every player template is tappable by default", () => {
  it("CompactPlayerCard is one 44px button that opens the player", () => {
    const { openPlayer } = withOpeners(<CompactPlayerCard player={chase} />);
    const tap = screen.getByRole("button", { name: "Open Ja'Marr Chase" });
    expect(tap.style.minHeight).toBe("var(--touch-target-min)");
    fireEvent.click(tap);
    expect(openPlayer).toHaveBeenCalledWith(expect.objectContaining({ id: "7564", name: "Ja'Marr Chase" }));
  });

  it("a player without an id stays plain, and nonInteractive opts out", () => {
    withOpeners(
      <>
        <CompactPlayerCard player={rookie} />
        <CompactPlayerCard player={chase} nonInteractive="inside a picker row that selects" testId="off" />
      </>,
    );
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("never nests a button inside a button (card inside a legacy trigger, avatar inside a card)", () => {
    const { container } = render(
      <PlayerIdentityTrigger identity={{ player_id: "7564", name: "Ja'Marr Chase" }}>
        <CompactPlayerCard player={chase} />
        <PlayerAvatarSlot player={chase} />
      </PlayerIdentityTrigger>,
    );
    expect(container.querySelectorAll("button button")).toHaveLength(0);
    expect(container.querySelectorAll("button")).toHaveLength(1);
  });

  it("the standalone avatar slot opens the player too", () => {
    const { openPlayer } = withOpeners(<PlayerAvatarSlot player={chase} tier="row" />);
    fireEvent.click(screen.getByRole("button", { name: "Open Ja'Marr Chase" }));
    expect(openPlayer).toHaveBeenCalledTimes(1);
  });

  it("trade cards open every player and every pick (sim offer card)", () => {
    const { openPlayer, openPick } = withOpeners(
      <TradeCompactCard
        mode="sim"
        title="KING TITUS"
        give={[{ key: "a", player: chase }]}
        get={[{ key: "p", pickLabel: "S10 2035 Round 1", pickId: "pick:2035:1:t2", pickDetail: "via KING TITUS" }]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open Ja'Marr Chase" }));
    expect(openPlayer).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Open S10 2035 Round 1" }));
    expect(openPick).toHaveBeenCalledWith({ id: "pick:2035:1:t2", label: "S10 2035 Round 1", detail: "via KING TITUS" });
  });

  it("PlayerAccordionRow: avatar and name open the player, the rest of the row expands", () => {
    const onToggle = vi.fn();
    const { openPlayer } = withOpeners(<PlayerAccordionRow player={chase} mode="desk" proj={12} open={false} onToggle={onToggle} />);
    const row = screen.getByTestId("player-accordion-row");
    const open = within(row).getAllByRole("button", { name: "Open Ja'Marr Chase" });
    expect(open).toHaveLength(2); // avatar + name
    fireEvent.click(open[0]);
    fireEvent.click(open[1]);
    expect(openPlayer).toHaveBeenCalledTimes(2);
    expect(onToggle).not.toHaveBeenCalled();
    fireEvent.click(within(row).getByRole("button", { name: /show details/ }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(row.querySelectorAll("button button")).toHaveLength(0);
  });

  it("PlayerAccordionRow with nonInteractive or no id is a single expand button", () => {
    withOpeners(<PlayerAccordionRow player={rookie} mode="desk" proj={1} open={false} onToggle={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});

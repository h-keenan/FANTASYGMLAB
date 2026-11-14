import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { PlayerAccordionRow, usePlayerAccordion } from "@/components/ui/PlayerAccordionRow";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { RankRow } from "@/components/ui/RankRow";
import { TradeCompactCard } from "@/components/ui/TradeCompactCard";
import { AVATAR_SIZE } from "@/lib/playerAnatomy";

const chase = { id: "7564", name: "Ja'Marr Chase", position: "WR", team: "CIN", age: 25 };
const gen = { id: null, name: "Zed Rookie", position: "RB" };

function List({ mode = "desk" as "desk" | "sim" }) {
  const acc = usePlayerAccordion();
  return (
    <>
      {[chase, { ...chase, id: "1", name: "Second Guy" }].map((p) => (
        <PlayerAccordionRow key={p.name} player={p} mode={mode} proj={19.8} value={92} trend={4} grade="A-" adp={3.4} ovr={88} open={acc.isOpen(p.name)} onToggle={() => acc.toggle(p.name)} onOpenProfile={() => {}} primaryAction={<button>Trade ideas</button>} />
      ))}
    </>
  );
}

describe("player templates always draw the avatar", () => {
  it("PlayerAvatarSlot uses the tier size token and falls back to initials without a photo", () => {
    render(<PlayerAvatarSlot player={gen} tier="card" />);
    const slot = screen.getByTestId("player-avatar-slot");
    expect(slot).toHaveStyle({ width: `${AVATAR_SIZE.card}px` });
    expect(slot).toHaveTextContent("ZR");
  });
  it("PlayerAccordionRow, CompactPlayerCard and RankRow render an avatar slot", () => {
    render(
      <>
        <PlayerAccordionRow player={chase} mode="desk" proj={1} open={false} onToggle={() => {}} />
        <CompactPlayerCard player={chase} />
        <RankRow player={chase} fraction={0.5} trailing="$12" />
      </>,
    );
    expect(screen.getAllByTestId("player-avatar-slot")).toHaveLength(3);
  });
  it("TradeCompactCard shows compact player cards for both sides and a fairness meter", () => {
    render(<TradeCompactCard title="Rival" give={[{ key: "a", player: chase, value: 100 }]} get={[{ key: "b", player: gen, value: 300 }, { key: "pick", pickLabel: "2027 R1" }]} />);
    expect(screen.getAllByTestId("compact-player-card")).toHaveLength(2);
    expect(screen.getAllByTestId("player-avatar-slot")).toHaveLength(2);
    expect(screen.getByTestId("fairness-meter")).toHaveTextContent("You win by ~67%");
  });
  it("sim trade card uses plain words and no numbers", () => {
    render(<TradeCompactCard mode="sim" title="Sim" give={[{ key: "a", player: chase, value: 100 }]} get={[{ key: "b", player: gen, value: 300 }]} />);
    expect(screen.getByTestId("fairness-meter")).toHaveTextContent("In your favor");
    expect(screen.queryByText("100")).toBeNull();
    expect(screen.queryByText("300")).toBeNull();
  });
});

describe("PlayerAccordionRow", () => {
  it("opens one row at a time in place", () => {
    render(<List />);
    const [a, b] = screen.getAllByRole("button", { expanded: false });
    fireEvent.click(a);
    expect(screen.getAllByTestId("row-expanded")).toHaveLength(1);
    fireEvent.click(b);
    expect(screen.getAllByTestId("row-expanded")).toHaveLength(1);
    expect(screen.getAllByTestId("player-accordion-row")[1]).toHaveAttribute("data-open", "true");
  });
  it("desk tile shows PROJ / VALUE / TREND / OVR; sim tile shows GRADE / ADP / PROJ and never value or OVR", () => {
    const { unmount } = render(<List />);
    fireEvent.click(screen.getAllByRole("button", { expanded: false })[0]);
    const desk = screen.getByTestId("row-expanded").textContent ?? "";
    expect(desk).toMatch(/PROJ/);
    expect(desk).toMatch(/VALUE/);
    expect(desk).toMatch(/TREND/);
    unmount();
    render(<List mode="sim" />);
    fireEvent.click(screen.getAllByRole("button", { expanded: false })[0]);
    const sim = screen.getByTestId("row-expanded").textContent ?? "";
    expect(sim).toMatch(/GRADE/);
    expect(sim).toMatch(/ADP/);
    expect(sim).not.toMatch(/VALUE|OVR|92|88/);
  });
});

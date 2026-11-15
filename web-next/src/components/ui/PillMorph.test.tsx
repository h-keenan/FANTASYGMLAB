import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PillMorph } from "@/components/ui/PillMorph";
import { PillOrb } from "@/components/ui/PillOrb";
import { simPillPlan, type PillContext } from "@/lib/bottomNav";

const orb = <PillOrb label="Team. Game menu" badge={2} popup onClick={() => {}} testId="sim-game-orb" />;
const draft: PillContext = {
  id: "sim-draft", label: "Draft panels", activeKey: "board", onSelect: vi.fn(),
  tabs: [{ key: "board", label: "Players" }, { key: "queue", label: "Queue" }],
  primary: { key: "auto-pick", label: "Auto-pick", glyph: "recommended", onPress: () => {} },
};

describe("PillMorph (one orb)", () => {
  it("shows exactly one orb beside the action row and no menu / ellipsis button", () => {
    render(<PillMorph segment={null} orb={orb}><button>Advance</button></PillMorph>);
    expect(document.querySelectorAll("[data-pill-orb]")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Advance" })).toBeInTheDocument();
    expect(screen.queryByTestId("pill-menu-close")).toBeNull();
    expect(screen.queryByTestId("pill-menu")).toBeNull();
    expect(document.querySelector(".pill-icon-btn")).toBeNull();
    expect(screen.getByTestId("pill-morph")).toHaveAttribute("data-mode", "global");
  });

  it("swaps the row for a tabbed segment while the same orb stays put", () => {
    const plan = simPillPlan({ context: draft, simToAvailable: true });
    render(<PillMorph segment={plan.segment} orb={orb}><button>Advance</button></PillMorph>);
    expect(screen.getByTestId("pill-morph")).toHaveAttribute("data-mode", "context");
    expect(screen.getByRole("tablist", { name: "Draft panels" })).toBeInTheDocument();
    expect(screen.getByTestId("pill-primary")).toHaveAttribute("aria-label", "Auto-pick");
    expect(document.querySelectorAll("[data-pill-orb]")).toHaveLength(1);
    fireEvent.click(screen.getByRole("tab", { name: "Queue" }));
    expect(draft.onSelect).toHaveBeenCalledWith("queue");
  });
});

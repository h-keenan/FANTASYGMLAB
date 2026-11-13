import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlayerAvatar } from "./PlayerAvatar";
import { SimPlayerChip, SimSheet } from "./SimGameParts";

describe("SimPlayerChip", () => {
  it("shows the Sleeper headshot, position badge, team and Out chip for an injured player", () => {
    const { container } = render(
      <SimPlayerChip player={{ id: "4046", headshot_id: "4046", name: "Patrick Mahomes", pos: "QB", team: "KC", status: "out", out_weeks: 3 }} />,
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe("https://sleepercdn.com/content/nfl/players/4046.jpg");
    expect(screen.getByText("Patrick Mahomes")).toBeInTheDocument();
    expect(screen.getByText("KC")).toBeInTheDocument();
    expect(screen.getByTestId("player-injury-badge")).toBeInTheDocument();
  });

  it("falls back to initials in a same-size box when the id has no photo (synthetic players)", () => {
    const { container } = render(<SimPlayerChip player={{ id: "p0001", headshot_id: null, name: "Jaxon Smith", pos: "WR", team: "DAL" }} size={32} />);
    expect(container.querySelector("img")).toBeNull();
    const ring = container.querySelector("span[aria-hidden]") as HTMLElement;
    expect(ring.textContent).toBe("JS");
    expect(ring.style.width).toBe("calc(32px * var(--sim-scale, 1))");
    expect(ring.style.height).toBe("calc(32px * var(--sim-scale, 1))");
  });

  it("uses the team code for a defense", () => {
    const { container } = render(<SimPlayerChip player={{ id: "DEF-NYG", name: "NYG D/ST", pos: "DEF", team: "NYG" }} />);
    expect(container.querySelector("span[aria-hidden]")?.textContent).toBe("NYG");
  });
});

describe("SimPlayerChip hidePosition", () => {
  const rb = { id: "p0003", headshot_id: null, name: "Ray Back", pos: "RB" as const, team: "CHI" };
  it("keeps the position chip by default and drops it when the slot already says it", () => {
    const shown = render(<SimPlayerChip player={rb} />);
    expect(shown.container.querySelector(".position-badge")).not.toBeNull();
    const hidden = render(<SimPlayerChip player={rb} hidePosition />);
    expect(hidden.container.querySelector(".position-badge")).toBeNull();
    expect(hidden.container.textContent).toContain("Ray Back");
  });
});

describe("PlayerAvatar fallback", () => {
  it("swaps to initials when the photo fails, and retries for a recycled row with a new id", () => {
    const { container, rerender } = render(<PlayerAvatar playerId="1" fallbackLabel="AB" size={40} />);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toBe("AB");
    rerender(<PlayerAvatar playerId="2" fallbackLabel="CD" size={40} />);
    expect(container.querySelector("img")).not.toBeNull();
  });

  it("omits initials in tiny avatars", () => {
    const { container } = render(<PlayerAvatar playerId={null} fallbackLabel="AB" size={20} />);
    expect(container.textContent).toBe("");
  });
});

describe("SimSheet", () => {
  it("renders into document.body (viewport-centered), focuses itself, and closes on Escape and backdrop", () => {
    const onClose = vi.fn();
    const { container, unmount } = render(
      <div style={{ transform: "translateY(1px)" }}>
        <SimSheet title="Claim Test" onClose={onClose}>
          <button type="button">inside</button>
        </SimSheet>
      </div>,
    );
    const dialog = screen.getByRole("dialog");
    expect(container.contains(dialog)).toBe(false);
    expect(document.body.contains(dialog)).toBe(true);
    expect(document.activeElement).toBe(dialog);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.mouseDown(screen.getByTestId("sim-sheet-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(2);
    unmount();
  });
});

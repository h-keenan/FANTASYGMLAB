import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimRealismBanner, SimRealismModule, SimRealismSheet } from "./SimRealism";
import type { SimCtx } from "@/components/SimGameParts";
import type { SimGame, SimRealismInfo } from "@/lib/simGame";

const upgrade = vi.fn();
vi.mock("@/lib/api", () => ({ api: { realismUpgradeSimGame: (...a: unknown[]) => upgrade(...a) } }));

const rules = (over: Partial<SimRealismInfo> = {}): SimRealismInfo => ({
  rules_version: 0,
  eligible: true,
  pending: [
    { flag: "hint_v", value: 1, label: "Honest draft help", body: "Draft hints use public information only.", boundary: "now", when: "Right away" },
    { flag: "aging_v", value: 1, label: "Realistic aging and retirement", body: "Retirement follows position, age, role and production.", boundary: "season", when: "From the next offseason" },
  ],
  scheduled: [],
  in_force: {},
  history: [],
  note: "Past results stay as they were; new rules apply going forward.",
  ...over,
});

function makeCtx(info: SimRealismInfo | null) {
  const notify = vi.fn();
  const setGame = vi.fn();
  const bump = vi.fn();
  const ctx = {
    gameId: "g1",
    game: { id: "g1", status: "in_season", settings: { hint_v: 0 }, rules: info } as unknown as SimGame,
    call: async (fn: () => Promise<unknown>) => fn(),
    setGame,
    bump,
    notify,
    tick: 0,
  } as unknown as SimCtx;
  return { ctx, notify, setGame, bump };
}

beforeEach(() => {
  upgrade.mockReset();
  window.localStorage.clear();
});

describe("SimRealism UI", () => {
  it("the confirm sheet previews each rule with when it starts, says past results stay, and only then updates", async () => {
    const { ctx, notify, setGame, bump } = makeCtx(rules());
    upgrade.mockResolvedValue({ upgraded: true, flags: ["hint_v", "aging_v"], settings: { hint_v: 1 }, rules: rules({ eligible: false, pending: [], rules_version: 1 }) });
    const onClose = vi.fn();
    render(<SimRealismSheet ctx={ctx} open onClose={onClose} />);
    expect(screen.getByText("Update game rules")).toBeInTheDocument();
    expect(screen.getByText("Honest draft help")).toBeInTheDocument();
    expect(screen.getByText("Right away")).toBeInTheDocument();
    expect(screen.getByText("From the next offseason")).toBeInTheDocument();
    expect(screen.getByTestId("sim-realism-note")).toHaveTextContent("Past results stay as they were; new rules apply going forward.");
    expect(upgrade).not.toHaveBeenCalled(); // opening the sheet changes nothing
    fireEvent.click(screen.getByTestId("sim-realism-confirm"));
    await waitFor(() => expect(upgrade).toHaveBeenCalledWith("g1"));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(setGame).toHaveBeenCalledWith(expect.objectContaining({ settings: { hint_v: 1 }, rules: expect.objectContaining({ rules_version: 1 }) }));
    expect(bump).toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("Rules updated: 2 new rules on."), "success");
  });

  it("cancel closes without calling the server", () => {
    const { ctx } = makeCtx(rules());
    const onClose = vi.fn();
    render(<SimRealismSheet ctx={ctx} open onClose={onClose} />);
    fireEvent.click(screen.getByText("Not now"));
    expect(onClose).toHaveBeenCalled();
    expect(upgrade).not.toHaveBeenCalled();
  });

  it("the Home banner shows for an old save, opens the sheet and can be dismissed for good", async () => {
    const { ctx } = makeCtx(rules());
    const { unmount } = render(<SimRealismBanner ctx={ctx} />);
    const banner = screen.getByTestId("sim-realism-banner");
    expect(banner).toHaveTextContent("Newer realism rules are available");
    fireEvent.click(screen.getByText("Review"));
    expect(screen.getByTestId("sim-realism-sheet")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Not now"));
    fireEvent.click(screen.getByLabelText("Dismiss"));
    // Dismissing collapses the banner away (it plays its exit), then it is gone.
    await waitFor(() => expect(screen.queryByTestId("sim-realism-banner")).toBeNull());
    unmount();
    render(<SimRealismBanner ctx={ctx} />);
    expect(screen.queryByTestId("sim-realism-banner")).toBeNull(); // still dismissed on the next visit
  });

  it("no banner for a current save or an older server", () => {
    render(<SimRealismBanner ctx={makeCtx(rules({ eligible: false, pending: [] })).ctx} />);
    expect(screen.queryByTestId("sim-realism-banner")).toBeNull();
    render(<SimRealismBanner ctx={makeCtx(null).ctx} />);
    expect(screen.queryByTestId("sim-realism-banner")).toBeNull();
  });

  it("the menu module lists what changes and opens the sheet; a current save shows it is up to date", () => {
    const { ctx } = makeCtx(rules());
    const { unmount } = render(<SimRealismModule ctx={ctx} />);
    fireEvent.click(screen.getByRole("button", { name: /Update game rules/i }));
    expect(screen.getByText("Honest draft help")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("sim-realism-open"));
    expect(screen.getByTestId("sim-realism-sheet")).toBeInTheDocument();
    unmount();
    render(<SimRealismModule ctx={makeCtx(rules({ eligible: false, pending: [], rules_version: 1 })).ctx} />);
    expect(screen.getByTestId("sim-realism-module")).toHaveTextContent("Up to date");
  });
});

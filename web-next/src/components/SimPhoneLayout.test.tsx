import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Collapsible } from "./Collapsible";
import { SimDraftRow } from "./SimDraftBoard";
import { SimFinalView } from "./SimGameRecap";
import { SimOpenPlayerContext, SimPlayerChip, type SimCtx } from "./SimGameParts";
import { api } from "@/lib/api";
import type { SimGamePlayer } from "@/lib/simGame";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getSimGameResult: vi.fn() } };
});

const player = (over: Partial<SimGamePlayer> = {}): SimGamePlayer =>
  ({ id: "4046", headshot_id: "4046", name: "Pat Mahomes", pos: "QB", team: "KC", age: 29, adp: 40, value: 80, projection: 20, floor: 10, ceiling: 30, status: "healthy", out_weeks: 0, bye_week: 9, ...over }) as SimGamePlayer;

describe("Collapsible", () => {
  beforeEach(() => window.localStorage.clear());

  it("toggles with aria-expanded and remembers the choice per id", () => {
    const { unmount } = render(<Collapsible id="t.one" title="Injury report" defaultOpen={false}><p>Body text</p></Collapsible>);
    const button = screen.getByRole("button", { name: /Injury report/ });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Body text")).toBeNull();
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Body text")).toBeInTheDocument();
    expect(window.localStorage.getItem("fgl:sim-open:t.one")).toBe("1");
    unmount();
    render(<Collapsible id="t.one" title="Injury report" defaultOpen={false}><p>Body text</p></Collapsible>);
    expect(screen.getByRole("button", { name: /Injury report/ })).toHaveAttribute("aria-expanded", "true");
  });
});

describe("SimPlayerChip quick", () => {
  it("is not interactive by default and opens the game's player detail when quick", () => {
    const open = vi.fn();
    const { rerender } = render(
      <SimOpenPlayerContext.Provider value={open}><SimPlayerChip player={player()} /></SimOpenPlayerContext.Provider>,
    );
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<SimOpenPlayerContext.Provider value={open}><SimPlayerChip player={player()} quick /></SimOpenPlayerContext.Provider>);
    fireEvent.click(screen.getByRole("button", { name: /Pat Mahomes.*Open player details/ }));
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("an explicit onOpen wins and does not bubble to a row handler", () => {
    const row = vi.fn();
    const open = vi.fn();
    render(<div onClick={row}><SimPlayerChip player={player()} onOpen={open} /></div>);
    fireEvent.click(screen.getByRole("button", { name: /Pat Mahomes/ }));
    expect(open).toHaveBeenCalled();
    expect(row).not.toHaveBeenCalled();
  });
});

describe("SimDraftRow", () => {
  it("shows the edge from value rank vs ADP (green steal, red reach) and four aligned stats", () => {
    const { rerender } = render(<SimDraftRow player={player({ adp: 40, value_rank: 22, adp_edge: 18, overall: 91 })} />);
    expect(document.querySelector("[data-stat=edge]")).toHaveTextContent("Edge ▲18");
    rerender(<SimDraftRow player={player({ adp: 10, value_rank: 25, adp_edge: -15 })} />);
    expect(document.querySelector("[data-stat=edge]")).toHaveTextContent("Edge ▼15");
    rerender(<SimDraftRow player={player({ adp: 20, value_rank: 21, adp_edge: -1, overall: 77 })} />);
    expect(document.querySelector("[data-stat=edge]")).toBeNull();
    // every number carries its caption
    expect(document.querySelector("[data-stat=proj]")).toHaveTextContent(/^Proj/);
    expect(document.querySelector("[data-stat=ovr]")).toHaveTextContent(/^OVR/);
    expect(document.querySelector("[data-stat=ovr]")?.querySelector("[aria-label*='overall rating']")).not.toBeNull();
    expect(screen.queryByText(/^val$/i)).toBeNull();
    expect(document.querySelector("[data-stat=adp]")).toHaveTextContent(/^ADP/);
  });
});

describe("SimDraftRow bye, injury and drafted states", () => {
  it("always shows the bye week in the meta line, warning-colored only when it is soon", () => {
    const { rerender } = render(<SimDraftRow player={player({ bye_week: 11 })} />);
    expect(screen.getByTestId("list-meta")).toHaveTextContent("Bye 11");
    expect(screen.getByText("Bye 11").style.fontWeight).toBe("");
    rerender(<SimDraftRow player={player({ bye_week: 2 })} />);
    expect(screen.getByText("Bye 2").style.fontWeight).toBe("700");
  });
  it("marks an injured player with the OUT chip and a note, and never dims the row", () => {
    render(<SimDraftRow player={player({ status: "out", out_weeks: 4, ros_mean: 15, projection: 0 })} actions={<button>Draft</button>} />);
    expect(screen.getByText("OUT 4W")).toBeInTheDocument();
    const row = screen.getByTestId("draft-row");
    expect(row.style.opacity).toBe("");
    expect(screen.getByRole("button", { name: "Draft" })).toBeEnabled();
  });
  it("an optimistic pick shows Drafted and hides the actions", () => {
    render(<SimDraftRow player={player()} drafted actions={<button>Draft</button>} />);
    expect(screen.getByRole("status")).toHaveTextContent("Drafted");
    expect(screen.queryByRole("button", { name: "Draft" })).toBeNull();
  });
});

describe("Season in review on a phone", () => {
  const ctx = { gameId: "g1", game: { settings: { regular_weeks: 14 } } } as unknown as SimCtx;
  it("splits into Overview / Awards / Stats / Standings tabs", async () => {
    vi.mocked(api.getSimGameResult).mockResolvedValue({
      ok: true,
      result: {
        champion: { team_id: "3", name: "Team 3" },
        final_standings: [{ rank: 1, team_id: "3", name: "Team 3", is_you: true, wins: 9, losses: 5, ties: 0, pf: 1500, pa: 1400, playoff_result: "champion" }],
        grade: { letter: "B", score: 80, summary: { record: "9-5" }, components: [{ key: "record", label: "Record", score: 80, weight: 1 }] },
        decisions_that_mattered: [{ kind: "trade", title: "Week 3 trade", detail: "Helped." }],
      },
    } as never);
    render(<SimFinalView ctx={ctx} onNewGame={() => {}} onHub={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("final-result")).toBeTruthy());
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByLabelText("Final standings")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Standings" }));
    expect(screen.getByLabelText("Final standings")).toBeInTheDocument();
  });
});

describe("SimDraftRow in a rookie-only draft", () => {
  it("drops the redundant Rookie tag there, keeps it everywhere else", () => {
    const rookie = player({ age: 21 });
    const { rerender } = render(<SimDraftRow player={rookie} />);
    expect(screen.getByTestId("list-meta")).toHaveTextContent("Rookie");
    rerender(<SimDraftRow player={rookie} hideRookie />);
    expect(screen.getByTestId("list-meta")).not.toHaveTextContent("Rookie");
  });
});

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimBlockToggle, SimBlockView } from "./SimTradeBlock";
import type { SimCtx } from "./SimGameParts";
import { api } from "@/lib/api";
import type { SimBlockResponse, SimGame, SimGamePlayer } from "@/lib/simGame";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getSimBlock: vi.fn(), putSimBlock: vi.fn(), getSimGameTeam: vi.fn(), getSimPicks: vi.fn() } };
});

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function p(id: string, name: string, pos: SimGamePlayer["pos"], over: Partial<SimGamePlayer> = {}): SimGamePlayer {
  return { id, name, pos, team: "KC", age: 26, adp: 5, value: 60, overall: 80, projection: 12.3, floor: 5, ceiling: 20, status: "healthy", out_weeks: 0, bye_week: 9, owner: { type: "you", team_id: "3", name: "Me" }, ...over };
}

const game = { id: "g1", status: "in_season", week: 4, settings: { block_v: 1, slots: ["QB", "RB"] }, can_trade: true, you: { team_id: "3", name: "Me" } } as unknown as SimGame;
const ctx = (over: Partial<SimCtx> = {}) => ({ gameId: "g1", game, tick: 0, bump: vi.fn(), call: (fn: () => Promise<unknown>) => fn(), openPlayer: vi.fn(), openTeam: vi.fn(), notify: vi.fn(), ...over }) as unknown as SimCtx;

const block = (over: Partial<SimBlockResponse> = {}): SimBlockResponse => ({
  ok: true, reason: "", enabled: true, max_items: 8, offers_from_block: 1,
  mine: [{ asset: p("b1", "Blocked Ben", "WR", { block: { by: "3", mine: true, looking_for: "RB", why: "On your block" } }), looking_for: "RB", since_week: 3 }],
  league: [{ team_id: "7", name: "Rival Rovers", stance: "rebuilding", looking_for: "QB", needs: ["QB", "TE"], items: [{ asset: p("v1", "Vet Vince", "RB", { age: 31, owner: { type: "ai", team_id: "7", name: "Rival Rovers" }, block: { by: "7", mine: false, looking_for: "QB", why: "Selling a veteran" } }), why: "Selling a veteran" }] }],
  ...over,
});

describe("Trades > My block", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", players: [p("b1", "Blocked Ben", "WR"), p("c1", "Candidate Cal", "RB"), p("k1", "Kicker Kyle", "K")], ir: [], taxi: [] });
    mocked.getSimPicks.mockResolvedValue({ ok: true, reason: "", teams: [], you: [] });
  });

  it("shows your block with its summary, the chip on each row, who is shopping around the league and their needs", async () => {
    mocked.getSimBlock.mockResolvedValue(block());
    render(<SimBlockView ctx={ctx()} onMakeOffer={vi.fn()} />);
    expect(await screen.findByTestId("sim-block-summary")).toHaveTextContent("1 of 8 on your block · 1 offer from your block this week");
    const mine = screen.getByRole("region", { name: "My block" });
    expect(within(mine).getAllByRole("img", { name: /On the trade block: yours/ }).length).toBeGreaterThan(0); // the shared row's block glyph badge
    expect(within(mine).getByText("Blocked Ben")).toBeInTheDocument();
    const league = screen.getByRole("region", { name: "Around the league" });
    expect(league).toHaveTextContent("Rival Rovers");
    expect(league).toHaveTextContent("rebuilding");
    expect(league).toHaveTextContent("Wants QB");
    expect(league).toHaveTextContent("Needs QB, TE");
    expect(league).toHaveTextContent("Selling a veteran");
    expect(within(league).getAllByRole("img", { name: "On the trade block" }).length).toBeGreaterThan(0);
  });

  it("adds and removes assets and sets the looking-for position through the API; kickers are not offered", async () => {
    mocked.getSimBlock.mockResolvedValue(block());
    mocked.putSimBlock.mockResolvedValue(block());
    render(<SimBlockView ctx={ctx()} onMakeOffer={vi.fn()} />);
    await screen.findByTestId("sim-block-summary");
    expect(screen.queryByRole("button", { name: /Put Kicker Kyle on the block/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Put Candidate Cal on the block" }));
    await waitFor(() => expect(mocked.putSimBlock).toHaveBeenCalledWith("g1", { asset_id: "c1", on: true, looking_for: null }));
    fireEvent.click(screen.getAllByRole("tab", { name: "TE" })[0]);
    await waitFor(() => expect(mocked.putSimBlock).toHaveBeenCalledWith("g1", { asset_id: "b1", on: true, looking_for: "TE" }));
    mocked.putSimBlock.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(mocked.putSimBlock).toHaveBeenCalledWith("g1", { asset_id: "b1", on: false, looking_for: null }));
  });

  it("Make an offer from a shopping team seeds the builder with that team and the asked asset", async () => {
    mocked.getSimBlock.mockResolvedValue(block());
    const onMakeOffer = vi.fn();
    render(<SimBlockView ctx={ctx()} onMakeOffer={onMakeOffer} />);
    fireEvent.click(await screen.findByRole("button", { name: "Make an offer to Rival Rovers" }));
    expect(onMakeOffer).toHaveBeenCalledWith("7", "v1");
  });

  it("a game from before the block says so instead of showing an empty tool", async () => {
    mocked.getSimBlock.mockResolvedValue({ ok: true, reason: "", enabled: false, mine: [], league: [] });
    render(<SimBlockView ctx={ctx()} onMakeOffer={vi.fn()} />);
    expect(await screen.findByText("No trade block in this game")).toBeInTheDocument();
  });

  it("the player sheet's toggle only appears for your own players in a block game, and flips through the API", async () => {
    mocked.getSimBlock.mockResolvedValue(block({ mine: [] }));
    mocked.putSimBlock.mockResolvedValue(block());
    const c = ctx();
    const { rerender } = render(<SimBlockToggle ctx={c} player={p("c1", "Candidate Cal", "RB")} />);
    fireEvent.click(await screen.findByRole("button", { name: "Put on the block" }));
    await waitFor(() => expect(mocked.putSimBlock).toHaveBeenCalledWith("g1", { asset_id: "c1", on: true }));
    expect(await screen.findByRole("button", { name: "Take off the block" })).toBeInTheDocument();
    rerender(<SimBlockToggle ctx={c} player={p("x", "Their Guy", "RB", { owner: { type: "ai", team_id: "7", name: "R" } })} />);
    expect(screen.queryByRole("button", { name: /block/ })).toBeNull();
    rerender(<SimBlockToggle ctx={ctx({ game: { ...game, settings: { ...game.settings, block_v: 0 } } as SimGame })} player={p("c1", "Candidate Cal", "RB")} />);
    expect(screen.queryByRole("button", { name: /block/ })).toBeNull();
  });
});

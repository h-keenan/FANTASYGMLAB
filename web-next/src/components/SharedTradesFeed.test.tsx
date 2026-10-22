import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SharedTradesFeed } from "./SharedTradesFeed";
import { ShareToCommunityToggle } from "./ShareToCommunityToggle";
import type { SharedCommunityTrade, TradeVerdict } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  getSharedCommunityTrades: vi.fn(),
  shareCommunityTrade: vi.fn(),
  deleteSharedCommunityTrade: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
});

function trade(overrides: Partial<SharedCommunityTrade> = {}): SharedCommunityTrade {
  return {
    id: "t1",
    display_name: "Anonymous",
    send: [{ asset_type: "player", name: "Sender Guy", position: "WR", player_id: "100" }],
    receive: [{ asset_type: "pick", name: "2027 1st" }],
    grade: "ACCEPT",
    band: "LEAN ACCEPT",
    why: "Value gain at a spot of need.",
    created_at: "2026-10-22T00:00:00Z",
    mine: false,
    ...overrides,
  };
}

describe("SharedTradesFeed", () => {
  it("renders nothing when unavailable", () => {
    const { container } = render(
      <SharedTradesFeed available={false} trades={[trade()]} onDelete={vi.fn()} onReport={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows name, grade, why and lets others report (hiding it locally)", () => {
    const onReport = vi.fn();
    render(<SharedTradesFeed available trades={[trade({ display_name: "Coach Z" })]} onDelete={vi.fn()} onReport={onReport} />);
    expect(screen.getByText("Coach Z")).toBeInTheDocument();
    expect(screen.getByText("LEAN ACCEPT")).toBeInTheDocument();
    expect(screen.getByText("Value gain at a spot of need.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Report" }));
    expect(onReport).toHaveBeenCalledWith("t1");
    expect(screen.queryByText("Coach Z")).toBeNull();
  });

  it("lets the owner delete instead of report", () => {
    const onDelete = vi.fn();
    render(<SharedTradesFeed available trades={[trade({ mine: true })]} onDelete={onDelete} onReport={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Report" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith("t1");
  });
});

describe("ShareToCommunityToggle", () => {
  const verdict = { ui_verdict: "ACCEPT", band: "LEAN ACCEPT", rationale: "Because." } as TradeVerdict;
  const send = [{ asset_type: "player" as const, player_id: "1", name: "A" }];
  const receive = [{ asset_type: "player" as const, player_id: "2", name: "B" }];

  beforeEach(() => {
    Object.values(mocks).forEach((m) => m.mockReset());
  });

  it("is hidden when the feature is unavailable", async () => {
    mocks.getSharedCommunityTrades.mockResolvedValue({ ok: true, available: false, trades: [] });
    const { container } = render(<ShareToCommunityToggle verdict={verdict} sendAssets={send} receiveAssets={receive} />);
    await waitFor(() => expect(mocks.getSharedCommunityTrades).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("is off by default, sends nothing until Share, and removes on toggle off", async () => {
    mocks.getSharedCommunityTrades.mockResolvedValue({ ok: true, available: true, trades: [] });
    mocks.shareCommunityTrade.mockResolvedValue({ ok: true, trade: trade() });
    mocks.deleteSharedCommunityTrade.mockResolvedValue({ ok: true });
    render(<ShareToCommunityToggle verdict={verdict} sendAssets={send} receiveAssets={receive} />);
    const toggle = await screen.findByRole("switch");
    expect(toggle).not.toBeChecked();
    expect(mocks.shareCommunityTrade).not.toHaveBeenCalled();

    fireEvent.click(toggle);
    fireEvent.change(screen.getByLabelText("Display name (optional)"), { target: { value: "Coach Z" } });
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    await waitFor(() => expect(mocks.shareCommunityTrade).toHaveBeenCalledTimes(1));
    expect(mocks.shareCommunityTrade.mock.calls[0][0]).toMatchObject({
      grade: "ACCEPT",
      band: "LEAN ACCEPT",
      why: "Because.",
      display_name: "Coach Z",
    });

    await screen.findByText(/Shared\./);
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(mocks.deleteSharedCommunityTrade).toHaveBeenCalledWith("t1"));
  });
});

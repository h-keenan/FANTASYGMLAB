import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TradeOfferContent } from "./TradeOfferContent";
import { api, type TradeTargetOffer, type TradeTargetResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getTradeTargetOffers: vi.fn() } };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn(), trackUse: vi.fn() }));

const OFFER: TradeTargetOffer = {
  rank: 1,
  title: "Players and picks",
  send: [
    { kind: "player", id: "p1", label: "My WR", position: "WR", value: 3000 },
    { kind: "pick", id: "2027:2:1", label: "2027 Round 2", position: "PICK", value: 800 },
  ],
  receive: [{ kind: "player", id: "t1", label: "Their RB", position: "RB", value: 3900 }],
  package: {
    send: [
      { asset_type: "player", player_id: "p1", name: "My WR", position: "WR", score: 3000 },
      { asset_type: "pick", label: "2027 Round 2", score: 800 },
    ],
    receive: [{ asset_type: "player", player_id: "t1", name: "Their RB", position: "RB", score: 3900 }],
    value_edge: "",
    confidence: "",
  },
  send_value: 3800,
  receive_value: 3900,
  verdict: "FAIR",
  value_delta: 100,
  lineup_points: 8,
  posture_label: "",
  acceptance: { label: "Likely", reason: "The value is close to even and the return helps their roster." },
  why: ["This adds about 8 lineup points over Weeks 8-17.", "You send 3,800 in value and get 3,900 back."],
  they_gain: "",
  you_gain: "",
};

function respond(partial: Partial<TradeTargetResponse>) {
  vi.mocked(api.getTradeTargetOffers).mockResolvedValue({
    ok: true,
    status: "found",
    offers: [],
    is_premium: true,
    upsell: null,
    ...partial,
  });
}

async function renderContent(playerId = "t1") {
  render(<TradeOfferContent leagueId="L1" leagueName="Dynasty Overlords" playerId={playerId} lens="Dynasty" />);
  await act(async () => {});
}

describe("TradeOfferContent", () => {
  beforeEach(() => vi.mocked(api.getTradeTargetOffers).mockReset());

  it("shows each offer with its why, acceptance read and an Open in Trade Analyzer link", async () => {
    respond({ headline: "1 way to get Their RB from Rivals.", offers: [OFFER] });
    await renderContent();
    expect(api.getTradeTargetOffers).toHaveBeenCalledWith("L1", "t1", "auto", "Dynasty");
    expect(screen.getByTestId("offer-headline")).toHaveTextContent("1 way to get Their RB from Rivals.");
    expect(screen.getAllByTestId("offer-card")).toHaveLength(1);
    expect(screen.getByText("Likely to accept")).toBeInTheDocument();
    expect(screen.getByText(/adds about 8 lineup points/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open in Trade Analyzer" })).toHaveAttribute(
      "href",
      "/trade-analyzer/L1?name=Dynasty+Overlords&send=p1&receive=t1&sendPicks=2027:2:1",
    );
  });

  it("shows the plain-English price line on a closest offer", async () => {
    respond({
      headline: "No clean fit for Their RB, but these are the closest ways to get him from Rivals.",
      offers: [{ ...OFFER, closest: true, price_note: "You'd pay about 700 more than Their RB's value." }],
    });
    await renderContent();
    expect(screen.getByTestId("offer-price-note")).toHaveTextContent("You'd pay about 700 more than Their RB's value.");
    expect(screen.getByTestId("offer-headline")).toHaveTextContent("closest ways to get him");
  });

  it("shows the Pro upsell, not offers, for a locked caller", async () => {
    respond({ status: "locked", is_premium: false, upsell: { title: "Build an offer for any player", body: "Upgrade to Pro to unlock it." } });
    await renderContent();
    expect(screen.queryByTestId("offer-card")).toBeNull();
    expect(screen.getByText("Upgrade to Pro to unlock it.")).toBeInTheDocument();
  });

  it("says why there is no offer, and sends a free agent to Waivers instead of trading", async () => {
    respond({ status: "none", headline: "Every package we tried was too lopsided for one side." });
    await renderContent();
    expect(screen.getByText("Every package we tried was too lopsided for one side.")).toBeInTheDocument();
    expect(screen.queryByTestId("offer-card")).toBeNull();
  });

  it("offers Waivers for a free agent", async () => {
    respond({ status: "not_rostered", headline: "That player is a free agent, so there is no one to trade with. Check Waivers." });
    await renderContent();
    expect(screen.getByRole("button", { name: "Go to Waivers" })).toBeInTheDocument();
  });

  it("retries after a failed request", async () => {
    vi.mocked(api.getTradeTargetOffers).mockRejectedValueOnce(new Error("down"));
    await renderContent();
    expect(screen.getByText("down")).toBeInTheDocument();
    respond({ offers: [OFFER] });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    });
    expect(screen.getAllByTestId("offer-card")).toHaveLength(1);
  });

  it("does not call the API without a target", async () => {
    await renderContent("");
    expect(api.getTradeTargetOffers).not.toHaveBeenCalled();
    expect(screen.getByText("Pick a player on another team to build an offer for.")).toBeInTheDocument();
  });
});

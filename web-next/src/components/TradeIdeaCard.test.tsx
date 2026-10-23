import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ShareTradeButton } from "./TradeIdeaCard";
import { api, type TradeAsset, type TradeIdea } from "@/lib/api";
import { resetShareBlobCache } from "@/lib/useShareImage";
import * as analytics from "@/lib/analytics";

const PNG = () => new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" });

/** The PNG is pre-rendered when the card mounts; wait until it is cached so
 * the tap runs the activation-safe synchronous path. */
async function waitForPrerender() {
  await waitFor(() => expect(api.getTradeHubIdeaShareCardBlob).toHaveBeenCalled());
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTradeHubIdeaShareCardBlob: vi.fn(),
      recordTradeShare: vi.fn(),
    },
  };
});

/**
 * ShareTradeButton (TradeIdeaCard.tsx) closes the "share sheet never
 * actually attached an image" gap: it used to call
 * navigator.share({text, title}) only. Now it fetches the real branded
 * PNG (GET .../trade-hub/{recommendation_id}/share-card.png) and attaches
 * it via the Files-capable Web Share API when available, falling back to
 * the original text-only share/clipboard-copy path for anything that
 * can't do that — a browser missing navigator.share/canShare, an idea
 * with no recommendation_id, or a failed PNG fetch (e.g. a stale idea the
 * server 404s).
 */

function asset(overrides: Partial<TradeAsset>): TradeAsset {
  return {
    asset_type: "player",
    player_id: "p1",
    name: "Test Player",
    position: "RB",
    team: "SF",
    age: 25,
    score: 2000,
    tier: "starter",
    overall_rating: 88,
    ...overrides,
  };
}

function idea(overrides: Partial<TradeIdea> = {}): TradeIdea {
  return {
    partner_team_name: "Rival GM",
    partner_team_avatar_url: null,
    partner_team_archetype_label: "Rebuilding",
    partner_trade_tendency: "Neutral",
    rationale: "Clear value upgrade at a position of need.",
    trade_gain: 800,
    confidence_label: "High",
    market_realism_label: "Realistic",
    reasoning_tags: ["Need-Based"],
    package: {
      send: [asset({ player_id: "my-rb", name: "My Running Back" })],
      receive: [asset({ player_id: "opp-wr", name: "Opp Wide Receiver", position: "WR" })],
      value_edge: "+800",
      confidence: "High",
    },
    category: "Headline Recommendation",
    value_edge_band: "Favorable",
    impact_tag: "high_impact",
    landed_gm_target_player_ids: [],
    send_score: 1200,
    receive_score: 2000,
    recommendation_id: "rec-abc123",
    ...overrides,
  };
}

/** Jsdom doesn't define navigator.share/canShare/clipboard by default --
 * these helpers add/remove them per test as own, configurable properties
 * so each test can simulate a different browser capability without
 * leaking into the next test. */
function stubShare(impl?: (data: ShareData) => Promise<void>) {
  const fn = vi.fn(impl ?? (() => Promise.resolve()));
  Object.defineProperty(navigator, "share", { value: fn, configurable: true, writable: true });
  return fn;
}

function stubCanShare(impl: (data?: ShareData) => boolean) {
  const fn = vi.fn(impl);
  Object.defineProperty(navigator, "canShare", { value: fn, configurable: true, writable: true });
  return fn;
}

function removeShareApis() {
  delete (navigator as unknown as Record<string, unknown>).share;
  delete (navigator as unknown as Record<string, unknown>).canShare;
}

function stubClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
    writable: true,
  });
  return writeText;
}

describe("ShareTradeButton", () => {
  beforeEach(() => {
    resetShareBlobCache();
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockReset();
    vi.mocked(api.recordTradeShare).mockReset();
    vi.mocked(api.recordTradeShare).mockResolvedValue({ ok: true, reason: "" });
  });

  afterEach(() => {
    removeShareApis();
    delete (navigator as unknown as Record<string, unknown>).clipboard;
  });

  it("attaches the real branded PNG via the Files-capable Web Share API", async () => {
    const share = stubShare();
    stubCanShare(() => true);
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockResolvedValue(
      new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" }),
    );

    render(<ShareTradeButton idea={idea()} leagueId="league-1" strategy="retool" lens="Dynasty" />);
    await waitForPrerender();
    fireEvent.click(screen.getByRole("button"));
    // Activation-safe: share() ran synchronously inside the click handler.
    expect(share).toHaveBeenCalledTimes(1);

    expect(api.getTradeHubIdeaShareCardBlob).toHaveBeenCalledWith("league-1", "rec-abc123", "retool", "Dynasty");
    const shareArgs = share.mock.calls[0][0] as ShareData;
    expect(shareArgs.files).toHaveLength(1);
    expect(shareArgs.files?.[0].type).toBe("image/png");
    expect(shareArgs.title).toContain("Rival GM");
    expect(shareArgs.text).toBeTruthy();
  });

  it("tap before the image is ready shows Preparing, then a second-step Share image button", async () => {
    const share = stubShare();
    stubCanShare(() => true);
    let resolveBlob: (blob: Blob) => void = () => {};
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockReturnValue(
      new Promise((resolve) => {
        resolveBlob = resolve;
      }),
    );

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(screen.getByRole("button")).toBeDisabled());
    expect(screen.getByRole("button").textContent).toMatch(/preparing image/i);
    expect(share).not.toHaveBeenCalled();

    resolveBlob(PNG());

    await waitFor(() => expect(screen.getByRole("button").textContent).toMatch(/share image/i));
    expect(share).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button"));
    expect(share).toHaveBeenCalledTimes(1);
    expect((share.mock.calls[0][0] as ShareData).files).toHaveLength(1);
  });

  it("shows an inline message and records image_failed when the image cannot be built", async () => {
    stubShare();
    stubCanShare(() => true);
    const track = vi.spyOn(analytics, "trackUse").mockImplementation(() => {});
    const err = new Error("boom");
    err.name = "EncodingError";
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockRejectedValue(err);

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    const status = await screen.findByRole("status");
    expect(status.textContent).toMatch(/Couldn't build the image on this device/);
    expect(status.textContent).toMatch(/Sharing text instead/);
    expect(track).toHaveBeenCalledWith(
      "share",
      "image_failed",
      expect.objectContaining({ props: expect.objectContaining({ result: "EncodingError" }) }),
    );
    track.mockRestore();
  });

  it("falls back to the text copy when there's no recommendation to render a card for", async () => {
    removeShareApis();
    const writeText = stubClipboard();

    render(<ShareTradeButton idea={idea({ recommendation_id: undefined })} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(api.getTradeHubIdeaShareCardBlob).not.toHaveBeenCalled();
    await screen.findByText("Copied!");
  });

  it("saves the PNG instead of sharing text when canShare rejects the file", async () => {
    const share = stubShare();
    stubCanShare(() => false);
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockResolvedValue(
      new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" }),
    );

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    await screen.findByText("Copied!");
    expect(share).not.toHaveBeenCalled();
  });

  it("falls back to the text-only share when the PNG fetch fails (e.g. a stale/changed idea)", async () => {
    const share = stubShare();
    stubCanShare(() => true);
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockRejectedValue(new Error("not found"));

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    await waitForPrerender();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(share).toHaveBeenCalledTimes(1));
    const shareArgs = share.mock.calls[0][0] as ShareData;
    expect(shareArgs.files).toBeUndefined();
    expect(shareArgs.text).toBeTruthy();
  });

  it("skips the image fetch entirely when leagueId or recommendation_id is missing", async () => {
    stubShare();
    stubCanShare(() => true);

    render(<ShareTradeButton idea={idea({ recommendation_id: undefined })} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(navigator.share).toHaveBeenCalledTimes(1));
    expect(api.getTradeHubIdeaShareCardBlob).not.toHaveBeenCalled();
  });

  /**
   * Trade Outcomes: a completed share records the trade (POST
   * /v1/leagues/{id}/trade-outcomes) so "Did this trade happen?" can ask
   * about it later. Same payload and behaviour as mobile's
   * TradeSharePreviewModal.recordShare: picks dropped, one record per
   * completed share, nothing recorded for a cancelled share sheet.
   */
  const expectedRecord = {
    partnerTeamName: "Rival GM",
    send: [{ name: "My Running Back", position: "RB", player_id: "my-rb", value_score: 2000 }],
    receive: [{ name: "Opp Wide Receiver", position: "WR", player_id: "opp-wr", value_score: 2000 }],
    valueEdgeLabel: "Realistic",
    valuationLens: "Rebuild",
  };

  it("records the trade after a successful image share", async () => {
    stubShare();
    stubCanShare(() => true);
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockResolvedValue(
      new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" }),
    );

    render(<ShareTradeButton idea={idea()} leagueId="league-1" lens="Rebuild" />);
    await waitForPrerender();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(api.recordTradeShare).toHaveBeenCalledTimes(1));
    expect(api.recordTradeShare).toHaveBeenCalledWith("league-1", expectedRecord);
  });

  it("records the trade after a text share or a clipboard copy", async () => {
    removeShareApis();
    stubClipboard();

    render(<ShareTradeButton idea={idea()} leagueId="league-1" lens="Rebuild" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(api.recordTradeShare).toHaveBeenCalledWith("league-1", expectedRecord));
  });

  it("drops draft picks and empty player ids from the recorded trade", async () => {
    removeShareApis();
    stubClipboard();
    const withPick = idea({
      package: {
        send: [
          asset({ player_id: "", name: "Hand Built", score: null }),
          asset({ asset_type: "pick", player_id: undefined, name: "2027 1st" }),
        ],
        receive: [],
        value_edge: "+0",
        confidence: "Low",
      },
      market_realism_label: "",
    });

    render(<ShareTradeButton idea={withPick} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(api.recordTradeShare).toHaveBeenCalledTimes(1));
    expect(api.recordTradeShare).toHaveBeenCalledWith("league-1", {
      partnerTeamName: "Rival GM",
      send: [{ name: "Hand Built", position: "RB", player_id: undefined, value_score: undefined }],
      receive: [],
      valueEdgeLabel: "Trade Hub idea",
      valuationLens: "Dynasty",
    });
  });

  it("records each completed share, like mobile (no dedupe)", async () => {
    removeShareApis();
    stubClipboard();

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(api.recordTradeShare).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(api.recordTradeShare).toHaveBeenCalledTimes(2));
  });

  it("records nothing when the image share sheet is cancelled", async () => {
    stubShare(() => Promise.reject(new DOMException("cancelled", "AbortError")));
    stubCanShare(() => true);
    vi.mocked(api.getTradeHubIdeaShareCardBlob).mockResolvedValue(
      new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: "image/png" }),
    );

    render(<ShareTradeButton idea={idea()} leagueId="league-1" />);
    await waitForPrerender();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(navigator.share).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button")).not.toBeDisabled());
    expect(api.recordTradeShare).not.toHaveBeenCalled();
  });

  it("records nothing without a leagueId", async () => {
    removeShareApis();
    const writeText = stubClipboard();

    render(<ShareTradeButton idea={idea()} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(api.recordTradeShare).not.toHaveBeenCalled();
  });
});

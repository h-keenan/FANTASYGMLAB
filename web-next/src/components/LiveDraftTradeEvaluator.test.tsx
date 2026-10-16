import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LiveDraftTradeEvaluator } from "./LiveDraftTradeEvaluator";
import type { LiveDraftPickRow } from "@/lib/api";
import { api } from "@/lib/api";

/**
 * jsdom/testing-library substitute for live E2E (no Supabase/Sleeper
 * credentials in this environment) — exercises the hypothetical mid-draft
 * Trade Evaluator (the last of the 4 deferred migration-sprint features)
 * against a mocked GET/POST .../trade-evaluator, mirroring
 * TradeAnalyzerContent.test.tsx's own pattern for the sibling builder.
 */

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getLiveDraftTradeEvaluatorOptions: vi.fn(),
      postLiveDraftTradeEvaluator: vi.fn(),
    },
  };
});

const DRAFTED_ROWS: LiveDraftPickRow[] = [
  {
    pick_no: 1,
    round: 1,
    round_pick: "1.01",
    player_id: "wr0",
    player_name: "Star Wideout",
    position: "WR",
    team: "KC",
    fantasy_team: "My Dynasty",
    is_mine: true,
  },
];

function renderEvaluator() {
  return render(<LiveDraftTradeEvaluator leagueId="league-1" draftId="draft-1" draftedRows={DRAFTED_ROWS} />);
}

describe("LiveDraftTradeEvaluator", () => {
  it("starts collapsed and only fetches remaining-pick options once opened", async () => {
    vi.mocked(api.getLiveDraftTradeEvaluatorOptions).mockResolvedValue({
      ok: true,
      reason: "",
      pick_data_stale: false,
      pick_options: [{ pick_key: "pick:2", label: "Pick 1.02 · Rd 1 · Rival Squad" }],
    });

    renderEvaluator();
    expect(api.getLiveDraftTradeEvaluatorOptions).not.toHaveBeenCalled();
    expect(screen.queryByText("Remaining picks")).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Evaluate a trade" }));
    });

    expect(api.getLiveDraftTradeEvaluatorOptions).toHaveBeenCalledWith("league-1", "draft-1");
    expect((await screen.findAllByText("Pick 1.02 · Rd 1 · Rival Squad")).length).toBe(2);
    expect(screen.getAllByText("Star Wideout (WR · My Dynasty)").length).toBe(2);
  });

  it("evaluates a selected pick-for-player package and renders the real verdict", async () => {
    vi.mocked(api.getLiveDraftTradeEvaluatorOptions).mockResolvedValue({
      ok: true,
      reason: "",
      pick_data_stale: false,
      pick_options: [{ pick_key: "pick:2", label: "Pick 1.02 · Rd 1 · Rival Squad" }],
    });
    vi.mocked(api.postLiveDraftTradeEvaluator).mockResolvedValue({
      ok: true,
      reason: "",
      stale_pick_keys: [],
      send_assets: [
        {
          asset_type: "pick",
          player_id: null,
          name: null,
          label: "2026 Round 1 (Pick 1.02) · Rival Squad",
          position: "PICK",
          team: null,
          age: null,
          score: 1200,
          injury_status: null,
          tier: null,
          season: "2026",
          round: "1",
          owner_team_name: "Rival Squad",
        },
      ],
      receive_assets: [
        {
          asset_type: "player",
          player_id: "wr0",
          name: "Star Wideout",
          label: "Star Wideout",
          position: "WR",
          team: "KC",
          age: 24,
          score: 6000,
          injury_status: null,
          tier: null,
          season: null,
          round: null,
          owner_team_name: null,
        },
      ],
      send_total: 1200,
      receive_total: 6000,
      delta: 4800,
      verdict: "Favorable",
    });

    renderEvaluator();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Evaluate a trade" }));
    });
    await screen.findAllByText("Pick 1.02 · Rd 1 · Rival Squad");

    // Send side: the remaining pick (first checklist instance).
    fireEvent.click(screen.getAllByText("Pick 1.02 · Rd 1 · Rival Squad")[0]);
    // Receive side: the drafted player (second checklist instance).
    fireEvent.click(screen.getAllByText("Star Wideout (WR · My Dynasty)")[1]);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Evaluate Trade" }));
    });

    expect(api.postLiveDraftTradeEvaluator).toHaveBeenCalledWith(
      "league-1",
      "draft-1",
      expect.objectContaining({
        sendPickKeys: ["pick:2"],
        receivePlayerIds: ["wr0"],
        lens: "Dynasty",
      }),
    );

    expect(await screen.findByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("+4,800")).toBeInTheDocument();
    expect(screen.getByText("Star Wideout")).toBeInTheDocument();
  });

  it("surfaces a stale-pick selection as a message instead of a verdict", async () => {
    vi.mocked(api.getLiveDraftTradeEvaluatorOptions).mockResolvedValue({
      ok: true,
      reason: "",
      pick_data_stale: false,
      pick_options: [
        { pick_key: "pick:2", label: "Pick 1.02 · Rd 1 · Rival Squad" },
        { pick_key: "pick:3", label: "Pick 2.01 · Rd 2 · My Dynasty" },
      ],
    });
    vi.mocked(api.postLiveDraftTradeEvaluator).mockResolvedValue({
      ok: true,
      reason: "stale_picks",
      stale_pick_keys: ["pick:2"],
    });

    renderEvaluator();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Evaluate a trade" }));
    });
    await screen.findAllByText("Pick 1.02 · Rd 1 · Rival Squad");

    fireEvent.click(screen.getAllByText("Pick 1.02 · Rd 1 · Rival Squad")[0]);
    fireEvent.click(screen.getAllByText("Pick 2.01 · Rd 2 · My Dynasty")[1]);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Evaluate Trade" }));
    });

    const staleMessage = await screen.findByText(/These picks were just selected and can no longer be evaluated/);
    expect(staleMessage).toBeInTheDocument();
    expect(staleMessage.textContent).toContain("Pick 1.02 · Rd 1 · Rival Squad");
  });
});

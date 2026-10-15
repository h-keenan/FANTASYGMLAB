import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlayerCompareContent } from "./PlayerCompareContent";
import type { QuickViewModel, QuickViewResponse, RankedPlayer } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getPlayerQuickView: vi.fn(),
    },
  };
});

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Player One",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 12,
    position_rank: 4,
    rank_unavailable_reason: null,
    opportunity_label: "Lead Receiver",
    overall_rating: 72,
    ...overrides,
  };
}

function model(overrides: Partial<QuickViewModel>): QuickViewModel {
  return {
    market_score: 80,
    opportunity_score: 70,
    scarcity_score: 60,
    role_score: 90,
    age_score: 75,
    age_score_label: "Age Score",
    opportunity_confidence: 85,
    workload_trend: null,
    usage_trend: null,
    decision_fit_narrative: null,
    ...overrides,
  };
}

function quickViewResult(m: QuickViewModel): QuickViewResponse {
  return { ok: true, stats: null, bio: null, model: m, reason: "" };
}

const PLAYER_A = player({ player_id: "p1", name: "Player One", score: 1500, overall_rank: 12, position_rank: 4, age: 24 });
const PLAYER_B = player({ player_id: "p2", name: "Player Two", score: 1200, overall_rank: 30, position_rank: 10, age: 27 });
const POOL = [PLAYER_A, PLAYER_B, player({ player_id: "p3", name: "Player Three" })];

describe("PlayerCompareContent", () => {
  it("shows the base player and an opponent picker when no second player is chosen yet", () => {
    render(<PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    expect(screen.getByText("Player One")).toBeInTheDocument();
    expect(screen.getByText("Choose an opponent below.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search for a player to compare...")).toBeInTheDocument();
    expect(screen.getByText("Player Two")).toBeInTheDocument();
  });

  it("never offers the base player as their own opponent", () => {
    render(<PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    // "Player One" appears once, in the base player's own identity card —
    // never a second time inside the candidate list below it.
    expect(screen.getAllByText("Player One")).toHaveLength(1);
  });

  it("renders every row (identity + each stat row) on the same fixed 3-column grid, so values line up at the same x-position", async () => {
    vi.mocked(api.getPlayerQuickView).mockImplementation((playerId: string) =>
      Promise.resolve(quickViewResult(model(playerId === "p1" ? {} : { market_score: 40 }))),
    );

    render(
      <PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(screen.getByText("Market")).toBeInTheDocument());

    const gridRows = document.querySelectorAll("[data-compare-grid-row]");
    // Identity row + 4 Value & Rank rows + 6 Model Breakdown rows.
    expect(gridRows.length).toBeGreaterThanOrEqual(11);
    gridRows.forEach((row) => {
      expect(row.className).toContain("grid-cols-[1fr_6.5rem_1fr]");
    });
  });

  it("highlights the winning side of a numeric row without relying on color alone", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));

    render(
      <PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(screen.getByText("1,500")).toBeInTheDocument());
    // Player A's Value Score (1500) beats Player B's (1200).
    expect(screen.getAllByText("Better:").length).toBeGreaterThan(0);
  });

  it("lets the user reset back to the opponent picker via Compare someone else", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));

    render(
      <PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(screen.getByText("Market")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Compare someone else" }));

    expect(screen.getByText("Choose an opponent below.")).toBeInTheDocument();
  });

  it("selects an opponent from the picker and fetches both quick-view models", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue(quickViewResult(model({})));

    render(<PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={null} pool={POOL} />);

    fireEvent.click(screen.getByRole("button", { name: /Player Two/ }));

    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalledWith("p1"));
    expect(api.getPlayerQuickView).toHaveBeenCalledWith("p2");
  });

  it("omits the Model Breakdown section when neither side has model data", async () => {
    vi.mocked(api.getPlayerQuickView).mockResolvedValue({ ok: true, stats: null, bio: null, model: null, reason: "not_found" });

    render(
      <PlayerCompareContent leagueName="Dynasty Overlords" playerA={PLAYER_A} initialPlayerB={PLAYER_B} pool={POOL} />,
    );

    await waitFor(() => expect(api.getPlayerQuickView).toHaveBeenCalled());
    expect(screen.queryByText("Model Breakdown")).not.toBeInTheDocument();
    // Value & Rank always renders — it never depends on the quick-view fetch.
    expect(screen.getByText("Value & Rank")).toBeInTheDocument();
  });
});

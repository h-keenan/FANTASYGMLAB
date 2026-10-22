import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  PortfolioExposureView,
  sortExposurePlayers,
} from "./PortfolioExposureView";
import {
  api,
  type PortfolioExposurePlayer,
  type PortfolioExposureResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPortfolioExposure: vi.fn() } };
});

function player(
  overrides: Partial<PortfolioExposurePlayer>,
): PortfolioExposurePlayer {
  return {
    player_id: "1",
    name: "Bijan Robinson",
    position: "RB",
    team: "ATL",
    leagues_owned: 3,
    league_names: ["Alpha", "Beta", "Gamma"],
    leagues: [],
    share_of_leagues: 0.6,
    value: 25000,
    share_of_value: 0.1,
    ...overrides,
  };
}

function response(
  overrides: Partial<PortfolioExposureResponse> = {},
): PortfolioExposureResponse {
  return {
    ok: true,
    is_premium: true,
    lens: "Dynasty",
    upsell: null,
    skipped_leagues: [
      {
        league_id: "espn:1",
        league_name: "Espn One",
        reason: "espn_not_supported",
      },
    ],
    exposure: {
      league_count: 5,
      player_count: 2,
      total_value: 40000,
      players: [
        player({}),
        player({
          player_id: "2",
          name: "Puka Nacua",
          position: "WR",
          leagues_owned: 1,
          league_names: ["Delta"],
          share_of_leagues: 0.2,
          value: 30000,
        }),
      ],
      by_position: [
        { position: "RB", value: 25000, share_of_value: 0.62, roster_spots: 3 },
      ],
      concentration: { top_n: 5, top_share_of_value: 0.45, top_players: [] },
    },
    ...overrides,
  };
}

describe("PortfolioExposureView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sorts by leagues owned or by value", () => {
    const players = response().exposure!.players;
    expect(sortExposurePlayers(players, "leagues")[0].name).toBe(
      "Bijan Robinson",
    );
    expect(sortExposurePlayers(players, "value")[0].name).toBe("Puka Nacua");
  });

  it("shows the summary, the ESPN note and league names on expand", async () => {
    vi.mocked(api.getPortfolioExposure).mockResolvedValue(response());
    render(<PortfolioExposureView />);
    await waitFor(() =>
      expect(screen.getByText("Bijan Robinson")).toBeTruthy(),
    );
    expect(screen.getByText("45%")).toBeTruthy();
    expect(screen.getByText(/Espn One/)).toBeTruthy();
    expect(screen.queryByText("Alpha")).toBeNull();
    fireEvent.click(
      screen.getByLabelText("Bijan Robinson is in 3 of 5 leagues"),
    );
    expect(screen.getByText("Alpha")).toBeTruthy();
  });

  it("shows the upsell for a Free caller", async () => {
    vi.mocked(api.getPortfolioExposure).mockResolvedValue(
      response({
        is_premium: false,
        exposure: null,
        upsell: { title: "See your player exposure", body: "Pro feature." },
      }),
    );
    render(<PortfolioExposureView />);
    await waitFor(() =>
      expect(screen.getByText("See your player exposure")).toBeTruthy(),
    );
    expect(screen.queryByText("Bijan Robinson")).toBeNull();
  });
});

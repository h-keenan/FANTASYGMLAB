import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PortfolioPage from "./page";
import { api, type PortfolioIndexResponse, type PortfolioLeague, type PortfolioLeagueResponse } from "@/lib/api";
import { portfolioSnapshotKey } from "@/lib/portfolioSnapshot";

const ROUTER = { replace: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => ROUTER }));
const AUTH = { session: { user: { id: "user-1" } }, loading: false };
vi.mock("@/context/AuthContext", () => ({ useAuth: () => AUTH }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPortfolioIndex: vi.fn(), getPortfolioLeague: vi.fn(), removeSavedLeague: vi.fn() } };
});

const INDEX: PortfolioIndexResponse = {
  ok: true,
  is_premium: true,
  lens: "Dynasty",
  leagues: [],
  failed_leagues: [],
  upsell: null,
  saved_leagues: [
    { league_id: "a", league_name: "Alpha" },
    { league_id: "b", league_name: "Bravo" },
  ],
};

function row(id: string, signals = true): PortfolioLeague {
  return {
    league_id: id,
    league_name: `League ${id}`,
    team_name: `Team ${id}`,
    team_avatar_url: "",
    wins: 5,
    losses: 2,
    ties: 0,
    health_flag: "Stable",
    power_rank: 2,
    power_rank_tied: false,
    franchise_rank: 2,
    franchise_rank_tied: false,
    roster_value_rank: 2,
    roster_value_rank_tied: false,
    archetype: null,
    archetype_label: null,
    top_asset: null,
    top_item: null,
    top_items: signals
      ? [{ category: "need", headline: `Signal ${id}`, reason: "", destination: "my_team", recommendation_id: `r-${id}` } as never]
      : [],
  } as PortfolioLeague;
}

function response(id: string, signalsPending = false): PortfolioLeagueResponse {
  return {
    ok: true,
    is_premium: true,
    lens: "Dynasty",
    league: row(id, !signalsPending),
    failed_league: null,
    upsell: null,
    ...(signalsPending ? { signals_pending: true } : {}),
  };
}

describe("PortfolioPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(api.getPortfolioIndex).mockReset();
    vi.mocked(api.getPortfolioLeague).mockReset();
  });

  it("asks for headlines first, shows them with a signals skeleton, then fills the signals in", async () => {
    vi.mocked(api.getPortfolioIndex).mockResolvedValue(INDEX);
    vi.mocked(api.getPortfolioLeague).mockImplementation(async (id, _lens, _signal, deferSignals) =>
      response(id, Boolean(deferSignals)),
    );
    const { container } = render(<PortfolioPage />);

    await waitFor(() => expect(screen.getByText("Signal a")).toBeInTheDocument());
    expect(screen.getByText("Signal b")).toBeInTheDocument();
    expect(container.querySelector("[data-portfolio-signals-pending]")).toBeNull();
    const calls = vi.mocked(api.getPortfolioLeague).mock.calls.map(([id, , , defer]) => `${id}:${defer ? "headline" : "full"}`);
    expect(calls).toEqual(["a:headline", "b:headline", "a:full", "b:full"]);
    // The finished rows were stored for the next visit.
    const stored = JSON.parse(window.localStorage.getItem(portfolioSnapshotKey("user-1", "Dynasty")) ?? "{}");
    expect(Object.keys(stored.rows).sort()).toEqual(["a", "b"]);
  });

  it("paints a revisit from the stored Portfolio before the index answers, then revalidates it", async () => {
    const now = Date.now();
    window.localStorage.setItem(
      portfolioSnapshotKey("user-1", "Dynasty"),
      JSON.stringify({
        index: INDEX,
        rows: { a: { at: now - 10 * 60_000, data: response("a") }, b: { at: now - 10 * 60_000, data: response("b") } },
      }),
    );
    let releaseIndex: (value: PortfolioIndexResponse) => void = () => {};
    vi.mocked(api.getPortfolioIndex).mockReturnValue(new Promise((resolve) => (releaseIndex = resolve)));
    vi.mocked(api.getPortfolioLeague).mockImplementation(async (id) => response(id));

    render(<PortfolioPage />);
    // Instant: both cards from storage, no index response yet, no request for a league yet.
    expect(await screen.findByText("Signal a")).toBeInTheDocument();
    expect(screen.getByText("Signal b")).toBeInTheDocument();
    expect(api.getPortfolioLeague).not.toHaveBeenCalled();

    await act(async () => releaseIndex(INDEX));
    // Revalidation: one full request per stale league, never a headline request.
    await waitFor(() => expect(api.getPortfolioLeague).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.getPortfolioLeague).mock.calls.every(([, , , defer]) => !defer)).toBe(true);
    expect(screen.getByText("Signal a")).toBeInTheDocument();
  });

  it("leaves rows younger than the freshness window alone", async () => {
    const now = Date.now();
    window.localStorage.setItem(
      portfolioSnapshotKey("user-1", "Dynasty"),
      JSON.stringify({ index: INDEX, rows: { a: { at: now - 1000, data: response("a") }, b: { at: now - 1000, data: response("b") } } }),
    );
    vi.mocked(api.getPortfolioIndex).mockResolvedValue(INDEX);
    render(<PortfolioPage />);
    expect(await screen.findByText("Signal a")).toBeInTheDocument();
    await waitFor(() => expect(api.getPortfolioIndex).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.getPortfolioLeague).not.toHaveBeenCalled();
  });

  it("keeps the stored Portfolio on screen when the refresh fails", async () => {
    const now = Date.now();
    window.localStorage.setItem(
      portfolioSnapshotKey("user-1", "Dynasty"),
      JSON.stringify({ index: INDEX, rows: { a: { at: now - 600_000, data: response("a") }, b: { at: now - 600_000, data: response("b") } } }),
    );
    vi.mocked(api.getPortfolioIndex).mockRejectedValue(new Error("offline"));
    render(<PortfolioPage />);
    expect(await screen.findByText("Signal a")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByText("Signal a")).toBeInTheDocument();
    expect(screen.queryByText(/Could not load/i)).toBeNull();
  });
});

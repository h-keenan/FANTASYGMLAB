import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api, type DashboardResponse, type LeagueTeamRankingsResponse } from "@/lib/api";
import { deferred, mockLeagueType, renderWithLens, signedIn } from "@/lib/pageFetchTestKit";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));

const router = { replace: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useParams: () => ({ leagueId: "league-1" }),
  useSearchParams: () => new URLSearchParams("name=My League"),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, getDashboard: vi.fn(), getTeamRankings: vi.fn(), getLeague: vi.fn() },
  };
});

// The page's job here is fetching; render a marker that shows what it handed down.
vi.mock("@/components/DashboardContent", () => ({
  DashboardContent: ({ teamRankings }: { teamRankings?: Promise<unknown> }) => (
    <div data-testid="dashboard-content" data-has-rankings={String(Boolean(teamRankings))} />
  ),
}));

const dashboard = { items: [], entitlement: { hidden_count: 0 } } as unknown as DashboardResponse;
const rankings = { ok: true, teams: [] } as unknown as LeagueTeamRankingsResponse;

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(useAuth).mockReturnValue(signedIn);
});

describe("DashboardPage fetch order", () => {
  it("starts the Dashboard and team-rankings requests together, before either resolves", async () => {
    mockLeagueType(2);
    const dash = deferred<DashboardResponse>();
    const ranks = deferred<LeagueTeamRankingsResponse>();
    vi.mocked(api.getDashboard).mockReturnValue(dash.promise);
    vi.mocked(api.getTeamRankings).mockReturnValue(ranks.promise);

    renderWithLens(<DashboardPage />);

    await waitFor(() => expect(api.getDashboard).toHaveBeenCalledTimes(1));
    // Neither request has resolved, and the second one is already out.
    expect(api.getTeamRankings).toHaveBeenCalledTimes(1);
    expect(api.getTeamRankings).toHaveBeenCalledWith("league-1", "Dynasty");
    expect(api.getDashboard).toHaveBeenCalledWith("league-1", "Dynasty");

    await act(async () => {
      dash.resolve(dashboard);
      ranks.resolve(rankings);
    });
    expect(await screen.findByTestId("dashboard-content")).toHaveAttribute("data-has-rankings", "true");
  });

  it("fetches a redraft league once, with the redraft lens", async () => {
    mockLeagueType(0);
    vi.mocked(api.getDashboard).mockResolvedValue(dashboard);
    vi.mocked(api.getTeamRankings).mockResolvedValue(rankings);

    renderWithLens(<DashboardPage />);

    await screen.findByTestId("dashboard-content");
    expect(api.getDashboard).toHaveBeenCalledTimes(1);
    expect(api.getDashboard).toHaveBeenCalledWith("league-1", "Non-Dynasty");
    expect(api.getTeamRankings).toHaveBeenCalledTimes(1);
    expect(api.getTeamRankings).toHaveBeenCalledWith("league-1", "Non-Dynasty");
  });

  it("does not wait for league detection when an earlier visit remembered the type", async () => {
    window.localStorage.setItem("fgl.detectedLens.v1", JSON.stringify({ "league-1": "Non-Dynasty" }));
    vi.mocked(api.getLeague).mockReturnValue(deferred<never>().promise); // detection never answers
    vi.mocked(api.getDashboard).mockResolvedValue(dashboard);
    vi.mocked(api.getTeamRankings).mockResolvedValue(rankings);

    renderWithLens(<DashboardPage />);

    await screen.findByTestId("dashboard-content");
    expect(api.getDashboard).toHaveBeenCalledTimes(1);
    expect(api.getDashboard).toHaveBeenCalledWith("league-1", "Non-Dynasty");
  });
});

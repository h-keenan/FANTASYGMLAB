import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MyTeamPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api, type MyTeamResponse } from "@/lib/api";
import { deferred, mockLeagueType, renderWithLens, signedIn } from "@/lib/pageFetchTestKit";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));

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
    api: {
      ...actual.api,
      getMyTeam: vi.fn(),
      getMyTeamNeeds: vi.fn(),
      getKeepers: vi.fn(),
      getTeamRankings: vi.fn(),
      getLeague: vi.fn(),
    },
  };
});

vi.mock("@/components/MyTeamContent", () => ({
  MyTeamContent: ({
    teamRanking,
    leagueSize,
  }: {
    teamRanking: { team_name: string } | null;
    leagueSize: number;
  }) => <div data-testid="my-team" data-rank={teamRanking?.team_name ?? "none"} data-size={leagueSize} />,
}));

const myTeam = { roster_id: 7 } as unknown as MyTeamResponse;

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(useAuth).mockReturnValue(signedIn);
});

describe("MyTeamPage fetch order", () => {
  it("starts My Team, needs, keepers and team-rankings together, then matches the team", async () => {
    mockLeagueType(2);
    const team = deferred<MyTeamResponse>();
    const ranks = deferred<{ ok: boolean; teams: { roster_id: number; team_name: string }[] }>();
    vi.mocked(api.getMyTeam).mockReturnValue(team.promise);
    vi.mocked(api.getMyTeamNeeds).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getKeepers).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getTeamRankings).mockReturnValue(ranks.promise as never);

    renderWithLens(<MyTeamPage />);

    await waitFor(() => expect(api.getMyTeam).toHaveBeenCalledTimes(1));
    // Nothing has resolved yet, and the rankings request is already out
    // (it used to wait for My Team to return the roster id).
    expect(api.getTeamRankings).toHaveBeenCalledTimes(1);
    expect(api.getTeamRankings).toHaveBeenCalledWith("league-1", "Dynasty");
    expect(api.getMyTeamNeeds).toHaveBeenCalledTimes(1);
    expect(api.getKeepers).toHaveBeenCalledTimes(1);

    // The rankings can land before My Team does.
    await act(async () => {
      ranks.resolve({
        ok: true,
        teams: [
          { roster_id: 3, team_name: "Other" },
          { roster_id: 7, team_name: "Mine" },
        ],
      });
    });
    await act(async () => {
      team.resolve(myTeam);
    });

    const content = await screen.findByTestId("my-team");
    expect(content).toHaveAttribute("data-rank", "Mine");
    expect(content).toHaveAttribute("data-size", "2");
  });

  it("fetches a redraft league once, with the redraft lens", async () => {
    mockLeagueType(0);
    vi.mocked(api.getMyTeam).mockResolvedValue(myTeam);
    vi.mocked(api.getMyTeamNeeds).mockResolvedValue({} as never);
    vi.mocked(api.getKeepers).mockResolvedValue({} as never);
    vi.mocked(api.getTeamRankings).mockResolvedValue({ ok: true, teams: [] } as never);

    renderWithLens(<MyTeamPage />);

    await screen.findByTestId("my-team");
    for (const call of [api.getMyTeam, api.getMyTeamNeeds, api.getKeepers, api.getTeamRankings]) {
      expect(call).toHaveBeenCalledTimes(1);
      expect(call).toHaveBeenCalledWith("league-1", "Non-Dynasty");
    }
  });
});

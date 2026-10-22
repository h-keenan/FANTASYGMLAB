import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TradeHubPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api, type TradeHubResponse } from "@/lib/api";
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
    api: { ...actual.api, getTradeHub: vi.fn(), getTeamStance: vi.fn(), getLeague: vi.fn() },
  };
});

vi.mock("@/components/TradeHubContent", () => ({
  TradeHubContent: ({ data, lens }: { data: TradeHubResponse; lens: string }) => (
    <div data-testid="trade-hub" data-strategy={data.team_strategy} data-lens={lens} />
  ),
}));

function hub(strategy: string): TradeHubResponse {
  return { ok: true, ideas: [], reason: "", entitlement: null, team_strategy: strategy } as TradeHubResponse;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(useAuth).mockReturnValue(signedIn);
});

describe("TradeHubPage fetch order", () => {
  it("asks for the ideas immediately with strategy=auto and never waits on team-stance", async () => {
    mockLeagueType(2);
    const pending = deferred<TradeHubResponse>();
    vi.mocked(api.getTradeHub).mockReturnValue(pending.promise);
    vi.mocked(api.getTeamStance).mockReturnValue(new Promise(() => {})); // would hang the page if awaited

    renderWithLens(<TradeHubPage />);

    await waitFor(() => expect(api.getTradeHub).toHaveBeenCalledTimes(1));
    expect(api.getTradeHub).toHaveBeenCalledWith("league-1", "auto", "Dynasty");
    expect(api.getTeamStance).not.toHaveBeenCalled();

    pending.resolve(hub("contender"));
    expect(await screen.findByTestId("trade-hub")).toHaveAttribute("data-strategy", "contender");
  });

  it("falls back to team-stance then ideas when the server echoes strategy=auto unresolved", async () => {
    mockLeagueType(2);
    vi.mocked(api.getTradeHub).mockResolvedValueOnce(hub("auto")).mockResolvedValueOnce(hub("rebuild"));
    vi.mocked(api.getTeamStance).mockResolvedValue({ strategy: "rebuild" } as never);

    renderWithLens(<TradeHubPage />);

    expect(await screen.findByTestId("trade-hub")).toHaveAttribute("data-strategy", "rebuild");
    expect(api.getTeamStance).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.getTradeHub).mock.calls.map((call) => call[1])).toEqual(["auto", "rebuild"]);
  });

  it("fetches a redraft league once, with the redraft lens", async () => {
    mockLeagueType(0);
    vi.mocked(api.getTradeHub).mockResolvedValue(hub("retool"));

    renderWithLens(<TradeHubPage />);

    expect(await screen.findByTestId("trade-hub")).toHaveAttribute("data-lens", "Non-Dynasty");
    expect(api.getTradeHub).toHaveBeenCalledTimes(1);
    expect(api.getTradeHub).toHaveBeenCalledWith("league-1", "auto", "Non-Dynasty");
  });
});

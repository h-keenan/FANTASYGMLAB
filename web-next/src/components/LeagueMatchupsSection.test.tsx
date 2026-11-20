import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/dynamic", () => ({
  default: () => (props: { teamName: string }) => <div data-testid="sheet">{`sheet ${props.teamName}`}</div>,
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getLeagueMatchups: vi.fn() } };
});

import { LeagueMatchupsSection } from "@/components/LeagueMatchupsSection";
import { api, type LeagueMatchupsResponse } from "@/lib/api";

const side = (over: Record<string, unknown>) => ({
  roster_id: "1", team_name: "My Squad", owner_name: "me", avatar_url: "", record_label: "5-2", streak: 3, streak_label: "▲3W",
  standing_rank: 1, points: 98.2, projected_total: 118.4, win_probability: 0.71, is_mine: true, ...over,
});
const response = (over: Partial<LeagueMatchupsResponse> = {}): LeagueMatchupsResponse => ({
  ok: true, week: 11, current_week: 11, max_week: 18, reason: "", live: false,
  matchups: [{
    matchup_id: 3, game_state: "live",
    sides: [side({}), side({ roster_id: "2", team_name: "Their Squad", owner_name: "them", record_label: "3-4", streak: -2, streak_label: "▼2L", standing_rank: 6, points: 84.1, projected_total: 101.2, win_probability: 0.29, is_mine: false })],
  }],
  ...over,
} as LeagueMatchupsResponse);

describe("LeagueMatchupsSection", () => {
  beforeEach(() => vi.mocked(api.getLeagueMatchups).mockReset());

  it("renders a compact card per pair with points, projection, win bar and team links", async () => {
    vi.mocked(api.getLeagueMatchups).mockResolvedValue(response());
    await act(async () => { render(<LeagueMatchupsSection leagueId="L1" leagueName="Test" />); });
    expect(screen.getAllByTestId("league-matchup-card")).toHaveLength(1);
    expect(screen.getAllByTestId("league-matchup-points").map((n) => n.textContent)).toEqual(["98.2", "84.1"]);
    expect(screen.getByText("Proj 118.4")).toBeTruthy();
    expect(screen.getByText("71%")).toBeTruthy();
    expect(screen.getByText("29%")).toBeTruthy();
    expect(screen.getByText("#1 · 5-2 · ▲3W")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open Their Squad team sheet" })).toBeTruthy();
    expect(screen.getByText("VS")).toBeTruthy();
  });

  it("expands details and links only my own pair to the Matchup page", async () => {
    vi.mocked(api.getLeagueMatchups).mockResolvedValue(response());
    await act(async () => { render(<LeagueMatchupsSection leagueId="L1" leagueName="Test" />); });
    fireEvent.click(screen.getByRole("button", { name: /Details/ }));
    expect(screen.getByText("@them")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open my matchup" }).getAttribute("href")).toContain("/matchup/L1");
  });

  it("asks for another week from the select", async () => {
    vi.mocked(api.getLeagueMatchups).mockResolvedValue(response());
    await act(async () => { render(<LeagueMatchupsSection leagueId="L1" leagueName="Test" />); });
    await act(async () => { fireEvent.change(screen.getByLabelText("Matchups week"), { target: { value: "9" } }); });
    expect(api.getLeagueMatchups).toHaveBeenLastCalledWith("L1", 9);
  });

  it("renders nothing for a platform without the list", async () => {
    vi.mocked(api.getLeagueMatchups).mockResolvedValue(response({ matchups: [], reason: "unsupported_platform" }));
    await act(async () => { render(<LeagueMatchupsSection leagueId="L1" leagueName="Test" />); });
    expect(screen.queryByTestId("league-matchups")).toBeNull();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuessThePlayerLeaderboardContent } from "./GuessThePlayerLeaderboardContent";
import { api, type GuessThePlayerLeaderboardResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getGuessThePlayerLeaderboard: vi.fn(),
    },
  };
});

function response(overrides: Partial<GuessThePlayerLeaderboardResponse> = {}): GuessThePlayerLeaderboardResponse {
  return {
    ok: true,
    configured: true,
    stat_line: { entries: [] },
    name_match: { entries: [] },
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getGuessThePlayerLeaderboard).mockReset();
});

describe("GuessThePlayerLeaderboardContent", () => {
  it("shows a loading state before the fetch resolves", () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockReturnValue(new Promise(() => {}));
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);
    expect(screen.getByTestId("guess-the-player-leaderboard-loading")).toBeInTheDocument();
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockRejectedValue(new Error("network down"));
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("network down");
  });

  it("shows the not-configured empty state", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockResolvedValue(response({ configured: false }));
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);
    await screen.findByText(/leaderboard isn.t available right now/i);
  });

  it("shows the no-leaguemates empty state when configured but entries are empty", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockResolvedValue(response());
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);
    await screen.findByText(/nobody else in this league has a fantasydesk account yet/i);
  });

  it("renders ranked, populated entries with rank/streak/you badge", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockResolvedValue(
      response({
        stat_line: {
          entries: [
            { member_id: "m1", display_name: "Other Team", current_streak: 7, best_streak: 7, rank: 1, is_viewer: false },
            { member_id: "m2", display_name: "Viewer Team", current_streak: 2, best_streak: 4, rank: 2, is_viewer: true },
            {
              member_id: "m3",
              display_name: "No Streak Team",
              current_streak: 0,
              best_streak: 0,
              rank: 3,
              is_viewer: false,
            },
          ],
        },
      }),
    );
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);

    await screen.findByTestId("guess-the-player-leaderboard-entries");
    const rows = screen.getAllByText(/Team$/);
    expect(rows.map((row) => row.textContent)).toEqual(["Other Team", "Viewer Team", "No Streak Team"]);
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText(/Best 7/)).toBeInTheDocument();
    expect(screen.getByText(/Best 0/)).toBeInTheDocument();
  });

  it("switches between the two mini-games' leaderboards via the mode tabs", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockResolvedValue(
      response({
        stat_line: {
          entries: [
            { member_id: "m1", display_name: "Stat Line Leader", current_streak: 3, best_streak: 3, rank: 1, is_viewer: false },
          ],
        },
        name_match: {
          entries: [
            { member_id: "m2", display_name: "Name Match Leader", current_streak: 9, best_streak: 9, rank: 1, is_viewer: false },
          ],
        },
      }),
    );
    render(<GuessThePlayerLeaderboardContent leagueId="league-123" />);

    await screen.findByText("Stat Line Leader");
    expect(screen.queryByText("Name Match Leader")).not.toBeInTheDocument();

    screen.getByRole("tab", { name: /who is who/i }).click();

    await waitFor(() => expect(screen.getByText("Name Match Leader")).toBeInTheDocument());
    expect(screen.queryByText("Stat Line Leader")).not.toBeInTheDocument();
  });

  it("refetches when leagueId changes", async () => {
    vi.mocked(api.getGuessThePlayerLeaderboard).mockResolvedValue(response());
    const { rerender } = render(<GuessThePlayerLeaderboardContent leagueId="league-1" />);
    await waitFor(() => expect(api.getGuessThePlayerLeaderboard).toHaveBeenCalledWith("league-1"));

    rerender(<GuessThePlayerLeaderboardContent leagueId="league-2" />);
    await waitFor(() => expect(api.getGuessThePlayerLeaderboard).toHaveBeenCalledWith("league-2"));
  });
});

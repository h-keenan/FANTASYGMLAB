import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueWarmupProgress } from "./LeagueWarmupProgress";
import { SleeperImportForm } from "./SleeperImportForm";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      lookupSleeperLeagues: vi.fn(),
      linkSleeperUsername: vi.fn(),
      saveLeague: vi.fn(),
      getLeagueWarmupStatus: vi.fn(),
    },
  };
});

const stages = (roster: boolean, values: boolean, trades: boolean) => ({ roster, values, trades });

describe("LeagueWarmupProgress", () => {
  beforeEach(() => {
    vi.mocked(api.getLeagueWarmupStatus).mockReset();
  });

  it("shows real step completion while cold, then continues when done", async () => {
    vi.mocked(api.getLeagueWarmupStatus)
      .mockResolvedValueOnce({ ok: true, state: "running", stages: stages(true, false, false) })
      .mockResolvedValue({ ok: true, state: "done", stages: stages(true, true, true) });
    const onDone = vi.fn();
    render(<LeagueWarmupProgress leagueId="lg" onDone={onDone} />);

    await waitFor(() => expect(screen.getByText("Reading your roster").closest("li")).toHaveAttribute("data-done", "true"));
    expect(screen.getByText("Building trade ideas").closest("li")).toHaveAttribute("data-done", "false");
    expect(onDone).not.toHaveBeenCalled();
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("goes straight on when the league is already warm", async () => {
    vi.mocked(api.getLeagueWarmupStatus).mockResolvedValue({ ok: true, state: "none", stages: stages(false, false, false) });
    const onDone = vi.fn();
    render(<LeagueWarmupProgress leagueId="lg" onDone={onDone} />);
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("falls back to continuing when the status request fails or warm-up errors", async () => {
    vi.mocked(api.getLeagueWarmupStatus).mockRejectedValue(new Error("down"));
    const onDone = vi.fn();
    render(<LeagueWarmupProgress leagueId="lg" onDone={onDone} />);
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));

    vi.mocked(api.getLeagueWarmupStatus).mockResolvedValue({ ok: true, state: "error", stages: stages(true, false, false) });
    const onDoneError = vi.fn();
    render(<LeagueWarmupProgress leagueId="lg2" onDone={onDoneError} />);
    await waitFor(() => expect(onDoneError).toHaveBeenCalledTimes(1));
  });
});

describe("SleeperImportForm warm-up hand-off", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "u" } } as never,
      loading: false,
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      deleteAccount: vi.fn(),
      isGuest: false,
    });
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "ok",
      username: "someone",
      leagues: [{ league_id: "solo", name: "Solo", season: "2026", total_rosters: 12 }],
      message: "",
    });
    vi.mocked(api.linkSleeperUsername).mockResolvedValue({ ok: true } as never);
  });

  const connect = () => {
    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));
  };

  it("shows the progress steps for a cold league and continues once ready", async () => {
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 3, warming: true });
    vi.mocked(api.getLeagueWarmupStatus).mockResolvedValue({ ok: true, state: "done", stages: stages(true, true, true) });
    const onLeagueChosen = vi.fn();
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
    connect();
    await waitFor(() => expect(screen.getByTestId("league-warmup-progress")).toBeInTheDocument());
    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("solo", "Solo"));
  });

  it("skips the progress screen when the league is warm", async () => {
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 3, warming: false });
    const onLeagueChosen = vi.fn();
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
    connect();
    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("solo", "Solo"));
    expect(screen.queryByTestId("league-warmup-progress")).not.toBeInTheDocument();
  });
});
